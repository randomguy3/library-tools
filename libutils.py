# Copyright 2013  Alex Merry <dev@randomguy3.me.uk>
#
# Permission to use, copy, modify, and distribute this software
# and its documentation for any purpose and without fee is hereby
# granted, provided that the above copyright notice appear in all
# copies and that both that the copyright notice and this
# permission notice and warranty disclaimer appear in supporting
# documentation, and that the name of the author not be used in
# advertising or publicity pertaining to distribution of the
# software without specific, written prior permission.
#
# The author disclaim all warranties with regard to this
# software, including all implied warranties of merchantability
# and fitness.  In no event shall the author be liable for any
# special, indirect or consequential damages or any damages
# whatsoever resulting from loss of use, data or profits, whether
# in an action of contract, negligence or other tortious action,
# arising out of or in connection with the use or performance of
# this software.

import bisect
import csv
import codecs
import json
import stdnum.isbn
import urllib.request

class Book:
    def __init__(self, isbn = None):
        self.isbn = isbn
        self.read = None
        self.author = None
        self.title = None
        self.publisher = None
        self.comments = None
        self.location = None
        self.series = None
        self.anthology = None

    @classmethod
    def fromrow(cls, row):
        book = cls()
        book.isbn = row[0]
        book.read = (row[1] == 'yes')
        book.author = row[2]
        book.title = row[3]
        book.publisher = row[4]
        book.comments = row[5]
        book.location = row[6]
        book.series = row[7] if len(row) > 6 else ''
        book.anthology = (len(row) > 7 and row[8] == 'yes')
        return book

    @property
    def isbn(self):
        return self._isbn
    @isbn.setter
    def isbn(self, isbn):
        if not isbn:
            self._isbn = None
        else:
            stdnum.isbn.validate(isbn)
            self._isbn = stdnum.isbn.format(isbn,'-',convert=True)
    @isbn.deleter
    def isbn(self):
        del self._isbn

    @property
    def author_key(self):
        a = self.author
        # ignore "de", "van", etc when sorting
        first_cap = 0
        for i, c in enumerate(a):
            if c.isupper():
                first_cap = i
                break
        return a[first_cap::]

    @classmethod
    def writeheader(cls, csvwriter):
        csvwriter.writerow(["ISBN",
                            "Read",
                            "Author",
                            "Title",
                            "Publisher",
                            "Comments",
                            "Location",
                            "Series",
                            "Anthology"])

    def write(self, csvwriter):
        csvwriter.writerow([self.isbn or '',
                           ((self.read and "yes") or "no"),
                           self.author or '',
                           self.title or '',
                           self.publisher or '',
                           self.comments or '',
                           self.location or '',
                           self.series or '',
                           ((self.anthology and "yes") or "no")])

    def __eq__(self, other):
        if self.isbn or other.isbn:
            return self.isbn == other.isbn
        else:
            return self.author == other.author and self.title == other.title
    def __ne__(self, other):
        return not (self == other)
    def __hash__(self):
        if self.isbn:
            return hash(self.isbn)
        else:
            return hash((self.author,self.title))

    def author_sort_key(self):
        return (self.author_key, self.series, self.title)

    def title_sort_key(self):
        return (self.title, self.series, self.author_key)

    def __lt__(self, other):
        return self.author_sort_key() < other.author_sort_key()
    def __le__(self, other):
        return self == other or self.author_sort_key() <= other.author_sort_key()
    def __gt__(self, other):
        return self.author_sort_key() > other.author_sort_key()
    def __ge__(self, other):
        return self == other or self.author_sort_key() >= other.author_sort_key()

class LookupError(Exception):
    def __init__(self, msg, result=None, innerexception=None):
        self.strerror = msg
        self.result = result
        self.innerexception = innerexception
    def __repr__(self):
        rep = "LookupError("+repr(self.strerror)
        if not self.result is None:
            rep += ",result="+repr(self.result)
        if not self.innerexception is None:
            rep += ",innerexception="+repr(self.innerexception)
        return rep + ")"
    def __str__(self):
        return self.strerror

def lookup_isbn(isbn):
    try:
        gurl = ('https://www.googleapis.com/books/v1/volumes?' +
                '?key=AIzaSyCJ78Zd6pz0gT888typ-qHSOiT2GtOEiAE' +
                '&q=isbn:' + stdnum.isbn.compact(isbn))
        with urllib.request.urlopen(gurl) as urlf:
            result = urlf.readall()
            try:
                result = result.decode('utf-8')
                result = json.loads(result)
            except e:
                raise LookupError("Google returned an invalid response",result,e)
    except IOError as e:
        raise LookupError("Could not connect to Google to fetch ISBN information:"+
                " "+e.strerror, e)

    try:
        results = []
        if (result['totalItems'] > 0):
            for item in result['items']:
                r = Book()
                r.isbn = isbn
                volinfo = item['volumeInfo']
                authors = []
                if 'authors' in volinfo:
                    for gauthor in volinfo['authors']:
                        a = gauthor
                        author_sp = gauthor.rsplit(' ',1)
                        if len(author_sp) == 2:
                            a = author_sp[1] + ', ' + author_sp[0]
                        authors += [a]
                r.author = ' and '.join(authors)
                if 'title' in volinfo:
                    r.title = volinfo['title']
                if 'publisher' in volinfo:
                    r.publisher = volinfo['publisher']
                results.append(r)
        return results
    except e:
        raise LookupError("Failed to parse result for ISBN " + isbn, result, e)

class Library:
    def _read(self, fileobj):
        anthologies = []
        books = []
        csvin = csv.reader(fileobj)
        first = True
        for row in csvin:
            if first:
                first = False
                if row[0] == 'ISBN':
                    self._hasheader = True
                    continue
            book = Book.fromrow(row)
            if book.anthology:
                anthologies.append(book)
            else:
                books.append(book)
        books.sort()
        anthologies.sort(key=Book.title_sort_key)
        self.books = books
        self.anthologies = anthologies
        self._anthologykeys = None


    @classmethod
    def open(cls, filename, mode='r'):
        return cls(filename=filename, mode=mode)

    def __init__(self, filename=None, mode=None, fileobj=None):
        self.books = []
        self.anthologies = []
        self._anthologykeys = None
        self._hasheader = False
        self._filename = filename
        if mode is None:
            if fileobj is None:
                mode='r'
            else:
                if fileobj.readable() and fileobj.writable():
                    mode = 'r+'
                elif fileobj.readable():
                    mode = 'r'
                elif fileobj.writable():
                    mode = 'a'
        self._mode = mode
        if fileobj is None and not filename is None:
            fileobj = open(filename, newline='', encoding='utf-8', mode=self._mode)
        self._fileobj = fileobj
        if fileobj.writable():
            self._writer = csv.writer(fileobj)
        if not fileobj is None and fileobj.readable():
            self._read(self._fileobj)
        if not self._hasheader and len(self.books) == 0 and len(self.anthologies) == 0:
            Book.writeheader(self._writer)
            self._hasheader = True

    def __del__(self):
        del(self._fileobj)

    def __enter__(self):
        if not self._fileobj is None:
            self._fileobj = self._fileobj.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if not self._fileobj is None:
            return self._fileobj.__exit__(exc_type, exc_value, traceback)

    def reload(self):
        if self._fileobj is None:
            raise ValueError("No backing file")
        elif not self._fileobj.readable():
            raise ValueError("Backing file is not readable")
        else:
            self._read(self._fileobj)

    def _build_anth_keys(self):
        if self._anthologykeys is None:
            self._anthologykeys = [b.title_sort_key() for b in self.anthologies]

    def addbook(self, book):
        if book.anthology:
            self._build_anth_keys()
            idx = bisect.bisect(self._anthologykeys, book.title_sort_key())
            self.anthologies.insert(idx, book)
            self._anthologykeys.insert(idx, book.title_sort_key())
        else:
            bisect.insort(self.books, book)
        if not self._writer is None:
            book.write(self._writer)

    def index(self, book):
        if book.anthology:
            return self.anthologies.index(book)
        else:
            return self.books.index(book)

    def delbook(self, book):
        i = self.index(book)
        if i < 0:
            return
        if book.anthology:
            del self.anthologies[i]
            if self._anthologykeys:
                del self._anthologykeys[i]
        else:
            del self.books[i]

    def __contains__(self, book):
        if book.anthology:
            return book in self.anthologies
        else:
            return book in self.books

    def contains_isbn(self, isbn):
        return Book(isbn) in self

    def __len__(self):
        return len(self.anthologies) + len(self.books)

    def commit(self):
        if not self._fileobj is None:
            self._fileobj.flush()

class LocationMapper(dict):
    def __init__(self, default=None, mapping={}):
        self.default = default
        self.update(mapping)

    def __missing__(self, key):
        if self.default is None:
            return key
        else:
            return self.default

    @classmethod
    def defaultmapper(cls):
        return cls(default='On loan',
                mapping={'Home' : 'Home'})

