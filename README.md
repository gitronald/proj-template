# Project Template

This is a bash script that generates a project template for a research project. To ease your new project setup, add the following to your `.bashrc` or `.profile`:

```{bash}
new_proj() {
    URL='https://raw.githubusercontent.com/gitronald/proj-template/master/new_proj.sh'
    curl -s $URL | bash -s 
}
```

Now when you want to create a new project, you can call `new_proj <projectname>` from within bash and the script will create a new project template named `<projectname>` in your current directory. It should fail and gently ask you for a project name if you don't provide one. If it succeeds you will see something like this:

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
