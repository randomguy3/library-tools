This is a collection of scripts for maintaining a catalogue for a
personal library in CSV form.

It requires Python 3 (not sure what version) and the stdnum module.

Use personal-cat-entry to add things to your library; it will try to
warn you if you add the same book twice.

Use cat-to-html to generate a HTML version of a catalogue file.  You can
obscure the exact location information (for example, you can list
exactly who you loaned a book to in the CSV files, but just say "on
loan" on the generated web page).

