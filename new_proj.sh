# -*- coding: utf-8 -*-
# Make a dank new project, dealer's choice.

# echo -n "Enter project name: "
# read PROJ

# Check if no name (arg) provided
if [ $1 -eq 0 ]; then
    echo "No arguments provided"
    exit 1
fi

PROJ=$1
mkdir -p "$PROJ" 
for i in code data data-raw notebooks manuscript
    do mkdir -p "$PROJ/$i"
done

cat <<EOF >"$PROJ/README.md"
# $PROJ

EOF

# Useful file for Windows Bash (WSL)
cat <<EOF >"$PROJ/winmake.sh"
cd manuscript
make clean all
rm -f *.aux *.log *.out *.blg *.bbl *.cut

EOF

# Standard Latex Makefile
cat <<EOF >"$PROJ/manuscript/MakeFile"
LATEX=latex
BIBTEX=bibtex
BIBFILE=bibliography.bib
PAPER=main
#PDFLATEX=pdflatex -file-line-error -interaction=nonstopmode --shell-escape
PDFLATEX=pdflatex -file-line-error -halt-on-error

TEXFILES = \$(wildcard *.tex)

all: \$(PAPER).pdf

\$(PAPER).pdf: \$(TEXFILES) \$(BIBFILE)
    \$(PDFLATEX) \$(PAPER).tex
    \$(BIBTEX) \$(PAPER)
    \$(PDFLATEX) \$(PAPER).tex
    \$(PDFLATEX) \$(PAPER).tex

embed: \$(PAPER).pdf
    gs -dCompatibilityLevel=1.4 -dPDFSETTINGS=/screen -dCompressFonts=true -dSubsetFonts=true -dNOPAUSE -dBATCH -sDEVICE=pdfwrite -sOutputFile=\$(PAPER)_embed.pdf -c ".setpdfwrite <</NeverEmbed [ ]>> setdistillerparams" -f \$(PAPER).pdf
\n\
clean:
    rm -f *.dvi *.aux *.ps *~ *.log *.lot *.lof *.toc *.blg *.bbl *.pdf *.out

EOF

# Python specific replication script
cat <<EOF >"$PROJ/replicate.sh"
# Replication script

## Create virtualenv
virtualenv $PROJ/venv
source $PROJ/venv/bin/activate
pip install -r $PROJ/requirements.txt

## Clean data


## Analyze data

EOF

# Check if tree is installed
PKG_OK=$(dpkg-query -W --showformat='${Status}\n' tree|grep "install ok installed")

walk() {
        local indent="${2:-0}"
        printf "%*s%s\n" $indent '' "$1"
        for entry in "$1"/*; do
                [[ -d "$entry" ]] && walk "$entry" $((indent+4))
        done
}

# Display new proj dir structure with tree if installed else with walk indent
if [ "install ok installed" == "$PKG_OK" ];
    then
        tree "$PROJ"
    else
        walk "$PROJ"
        # ls -1d $PROJ $PROJ/*
fi
