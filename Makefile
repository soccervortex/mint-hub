PREFIX ?= /usr/local
DESTDIR ?=
SHAREDIR = $(DESTDIR)$(PREFIX)/share/mint-hub
BINDIR = $(DESTDIR)$(PREFIX)/bin
ICONDIR = $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps
APPDIR = $(DESTDIR)$(PREFIX)/share/applications

.PHONY: install uninstall

install:
	install -d $(SHAREDIR) $(SHAREDIR)/data $(BINDIR) $(ICONDIR) $(APPDIR)
	install -m644 *.py $(SHAREDIR)/
	install -m644 seed_catalog.json $(SHAREDIR)/
	install -m644 data/mint-hub.svg $(SHAREDIR)/data/
	printf '#!/bin/bash\nexec python3 $(PREFIX)/share/mint-hub/mint_hub.py "$$@"\n' > $(BINDIR)/mint-hub
	chmod 755 $(BINDIR)/mint-hub
	install -m644 data/mint-hub.svg $(ICONDIR)/mint-hub.svg
	install -m644 data/com.linuxmint.minthub.desktop $(APPDIR)/
	gtk-update-icon-cache -f $(DESTDIR)$(PREFIX)/share/icons/hicolor 2>/dev/null || true

uninstall:
	rm -rf $(SHAREDIR)
	rm -f $(BINDIR)/mint-hub
	rm -f $(APPDIR)/com.linuxmint.minthub.desktop
	rm -f $(ICONDIR)/mint-hub.svg
	gtk-update-icon-cache -f $(DESTDIR)$(PREFIX)/share/icons/hicolor 2>/dev/null || true
