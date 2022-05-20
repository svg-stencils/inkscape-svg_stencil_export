VERSION = 1.4
BASENAME = inkscape-svg_stencil_export
ZIPNAME = $(BASENAME)-$(VERSION).zip


copy2inkscape:
	@cp ./*.inx ./*.py ~/.config/inkscape/extensions

link2inkscape:
	@ln ./*.inx ./*.py ~/.config/inkscape/extensions

zip:
	zip -rj ./$(ZIPNAME) ./* -x ./$(ZIPNAME) -x ./*.png

bump:
	@echo "see README-release.md"
