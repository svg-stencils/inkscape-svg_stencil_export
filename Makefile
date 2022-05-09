VERSION = 1.2
BASENAME = inkscape-svg_stencil_export
ZIPNAME = $(BASENAME)-$(VERSION).zip

copy2inkscape:
	cp ./*.inx ./*.py ~/.config/inkscape/extensions

zip:
	zip -rj ./$(ZIPNAME) ./* -x ./$(ZIPNAME) -x ./*.png
