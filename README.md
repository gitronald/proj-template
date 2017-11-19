# Project Template

This is a bash script that generates a project template - including the directory structure and files that I typically use for projects. To ease your new project setup, add this to your `.bashrc` or `.profile`:

```{bash}
new_proj() {
    URL='https://raw.githubusercontent.com/gitronald/proj-template/master/new_proj.sh'
    curl -s $URL | bash -s 
}
```

And now when you want to create a new project, you can call `new_proj <projectname>`. It should fail and gently ask you for a project name if you don't provide one.