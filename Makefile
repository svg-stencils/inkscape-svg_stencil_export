VERSION = 1.1
BASENAME = inkscape-svg_stencil_export
ZIPNAME = $(BASENAME)-$(VERSION).zip

copy2inkscape:
	cp ./*.inx ./*.py ~/.config/inkscape/extensions

zip:
	zip -r ./$(ZIPNAME) ./* -x ./$(ZIPNAME)
