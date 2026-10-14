Fonts shipped with Phenix Rebirth (see src/fonts.py for where each one is used)

Audiowide-Regular.ttf      titles, main menu       (c) 2012 Astigmatic, SIL Open Font License 1.1  -> Audiowide-OFL.txt
Play-Bold.ttf              menus, help bar, HUD    (c) 2011 Jonas Hecksher, SIL Open Font License 1.1 -> Play-OFL.txt
Play-Regular.ttf           text read at length     (same)
DejaVuSans-Bold-Spare.ttf  the characters the others lack (arrows, symbols; Cyrillic for the titles)
                           DejaVu Sans Bold 2.37, Bitstream Vera licence + public domain -> DejaVu-LICENSE.txt
                           Unmodified glyphs, reduced to Latin, Greek, Cyrillic and symbol blocks with:
                           pyftsubset DejaVuSans-Bold.ttf --output-file=DejaVuSans-Bold-Spare.ttf --layout-features='*'
                             --name-IDs='*' --name-languages='*' --notdef-outline --glyph-names
                             --unicodes="U+0020-024F,U+0370-03FF,U+0400-04FF,U+1E00-1EFF,U+2000-206F,U+20A0-20BF,
                             U+2100-214F,U+2190-21FF,U+2200-22FF,U+2300-23FF,U+2460-24FF,U+2500-257F,U+2580-259F,
                             U+25A0-25FF,U+2600-26FF,U+2700-27BF"

Audiowide and Play come from https://github.com/google/fonts (ofl/audiowide, ofl/play), unmodified.
