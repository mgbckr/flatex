from importlib.resources import path
import click
import os
import re
import sys
import pathlib
import shutil

def is_input(line):
    """
    Determines whether or not a read in line contains an uncommented out
    \input{} statement. Allows only spaces between start of line and
    '\input{}'.
    """
    #tex_input_re = r"""^\s*\\input{[^}]*}""" # input only
    tex_input_re = r"""(^[^\%]*\\input{[^}]*})|(^[^\%]*\\include{[^}]*})"""  # input or include
    return re.search(tex_input_re, line)


def is_includegraphics(line):
    tex_input_re = r"""^[^\%]*includegraphics.*$"""  # input or include
    return re.search(tex_input_re, line)


def is_package(line):
    tex_input_re = r"""^[^\%]*usepackage.*$"""  # input or include
    return re.search(tex_input_re, line)


def get_input(line):
    """
    Gets the file name from a line containing an input statement.
    """
    tex_input_filename_re = r"""{[^}]*"""
    m = re.search(tex_input_filename_re, line)
    return m.group()[1:]


def get_figure_path(line):    
    tex_input_filename_re = r"""includegraphics[^\{]*{([^}]*)"""
    m = re.search(tex_input_filename_re, line)
    return pathlib.Path(m.group(1))


def get_package(line):
    tex_input_filename_re = r"""package[^\{]*{([^}]*)"""
    m = re.search(tex_input_filename_re, line)
    return m.group(1)
    

def combine_path(base_path, relative_ref):
    """
    Combines the base path of the tex document being worked on with the
    relate reference found in that document.
    """
    if (base_path != ""):
        os.chdir(base_path)
    # Handle if .tex is supplied directly with file name or not
    if relative_ref.endswith('.tex'):
        return os.path.join(base_path, relative_ref)
    else:
        return os.path.abspath(relative_ref) + '.tex'


def expand_file(
        base_file, current_path, include_bbl, include_figures, noline, nocomment):
    """
    Recursively-defined function that takes as input a file and returns it
    with all the inputs replaced with the contents of the referenced file.
    """
    output_lines = []
    f = open(base_file, "r",encoding='utf-8')
    for line in f:
        if is_input(line):
            new_base_file = combine_path(current_path, get_input(line))
            output_lines += expand_file(
                new_base_file, current_path, include_bbl, include_figures, noline, nocomment)
            if noline:
                pass
            else:
                output_lines.append('\n')  # add a new line after each file input
        elif include_bbl and line.startswith("\\bibliography") and (not line.startswith("\\bibliographystyle")):
            output_lines += bbl_file(base_file)
        elif nocomment and len(line.lstrip()) > 0 and line.lstrip()[0] == "%":
            pass
        else:
            output_lines.append(line)
    f.close()
    return output_lines


def post_processing(lines, nocomment):
    output_lines = []
    for line in lines:
        if nocomment and len(line.lstrip()) > 0 and line.lstrip()[0] == "%":
            # skip comment
            pass
        elif len(line.strip()) == 0:
            # skip line
            pass
        else:
            output_lines.append(line)
    return output_lines


def copy_resources(lines, output_path, copy_figures=True, copy_style=True):
    
    for line in lines:
        
        if copy_figures and is_includegraphics(line):
            
            # copy figure to build dir
            figure_path = get_figure_path(line)
            print("Copy figure:", figure_path)
            
            new_path = output_path / figure_path
            new_path.parent.mkdir(exist_ok=True, parents=True)
            
            # handle cases with no given extension 
            if figure_path.name.split(".")[-1] not in ["jpg", "png", "pdf", "jpeg", "tiff"]:
                for file in os.listdir(figure_path.parent):
                    if file.startswith(figure_path.name):
                        shutil.copy(figure_path.parent / file, new_path.parent / file)
            
            else:
                shutil.copy(figure_path, new_path)
            
        elif copy_style and is_package(line):
            
            package = get_package(line)
            style_path = pathlib.Path(package + ".sty")
            if style_path.exists():
                print("Copy style file:", style_path)
                new_path = output_path / style_path
                shutil.copy(style_path, new_path)
            
        else:
            pass


def bbl_file(base_file):
    """
    Return content of associated .bbl file
    """
    bbl_path = os.path.abspath(os.path.splitext(base_file)[0]) + '.bbl'
    return open(bbl_path).readlines()


@click.command()
@click.argument('base_file', type = click.Path())
@click.argument('output_root', type = click.Path(), default = "default")
@click.argument('output_filename', type = click.Path(), default = "default")
@click.option('--include_bbl/--no_bbl', default=True)
@click.option('--copy_figures/--no_figures', is_flag=True, default=True)
@click.option("--noline", is_flag = True, default=False)
@click.option("--nocomment", is_flag = True, default=True,
              help="remove any line that is a comment (this will preserve comments"
                                                  "at the same line as the text)")
def main(
        base_file, 
        output_root,
        output_filename,
        include_bbl, 
        copy_figures, 
        noline, 
        nocomment):
    """
    This "flattens" a LaTeX document by replacing all \input{X} lines w/ the
    text actually contained in X. See associated README.md for details.
    """
    current_path = os.path.split(base_file)[0]
    
    filename = pathlib.Path(base_file).name.split(".")[-2]
    if output_root is "default":
        output_root = pathlib.Path("build") / filename
    
    if output_filename is "default":
        output_filename = filename + ".tex"
        
    output_file = pathlib.Path(output_root, output_filename)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    
    lines = expand_file(
        base_file, current_path, include_bbl, copy_figures, noline, nocomment)
    lines = post_processing(lines, nocomment=nocomment)
    
    copy_resources(lines, output_path=output_file.parent, copy_figures=copy_figures)
    
    g = open(output_file, "w",encoding='utf-8')
    g.write(''.join(lines))
    g.close()
    
    return None

