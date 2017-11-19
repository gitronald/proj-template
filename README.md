# Project Template

This is a bash script and alias that automatically generates a directory template for a research project. The template is relatively tool and discipline agnostic, but includes traces of the tools I typically leverage the most these days: python (`replicate.sh` comes with code for creating a new virtual environment), and latex (`winmake.sh` and `manuscript/MakeFile` for compiling `.tex` and `.bib` files into a beautiful PDF on Windows 10 because I'm a kook). To streamline your new project setup, add this alias to your `.bashrc` or `.profile`:

```{bash}
alias new_proj='curl -s https://raw.githubusercontent.com/gitronald/proj-template/master/new_proj.sh | bash -s'
```

`curl -s` retrieves the script located in this repo, `new_proj.sh`.
`bash -s` runs that script on your system locally.

Now when you want to create a new project, you can call `new_proj <projectname>` from within bash and the script will create a new project template named `<projectname>` in your current directory. It should fail and gently ask you for a project name if you don't provide one, but if it doesn't then godspeed. If it does succeed you will see something like this:

```
rer@x:~/proj$ new_proj test
test
├── code
├── data
├── data-raw
├── manuscript
│   └── MakeFile
├── notebooks
├── README.md
├── replicate.sh
└── winmake.sh
```

And now you have a lovely new structure to fill with wonderful new bits and bytes of your creation and discovery. Happy researching.