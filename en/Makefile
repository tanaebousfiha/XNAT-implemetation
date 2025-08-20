TARGET=main
TEX_SOURCES=$(TARGET).tex content/*.tex

all: fast

fast: $(TEX_SOURCES)
	pdflatex $(TARGET)

bibtex: $(TARGET).aux
	pdflatex $(TARGET)
	bibtex $(TARGET)
	pdflatex $(TARGET)
	pdflatex $(TARGET)

index: $(TARGET).aux
	pdflatex $(TARGET)
	makeindex $(TARGET)
	pdflatex $(TARGET)
	pdflatex $(TARGET)

clean:
	rm -f *.log *.toc *.lof *.lot *.out *.pdf *.aux *.bbl *.blg *.idx *.ilg *.ind *.lol


