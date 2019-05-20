# generating html site using gitbook
# uses language-picker plugin, so need to install it
#
# npm install gitbook-plugin-language-picker
#

html: check
	gitbook build

pdf: check
	gitbook pdf
	
epub: check
	gitbook epub

check:
	@if [ -n "`which gitbook`" ] ; then \
		echo "gitbook found"  ; \
	else \
		echo "gitbook not found, try: npm install gitbook-cli -g"  ; \
		exit 1 ; \
	fi

serve:
	gitbook serve

all: html pdf epub

clean:
	rm -rf book*.pdf *.epub _book node_modules
