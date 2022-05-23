#! /usr/bin/env python

import sys
import inkex
from lxml import etree
import os
import subprocess
import tempfile
import shutil
import copy
import logging
import json

class Options():
    def __init__(self, svg_stencil_exporter):

        # self.mostLeft = 0
        # self.mostRight = 0
        # self.mostTop = 0
        # self.mostBottom = 0

        self.current_file = svg_stencil_exporter.options.input_file

        self.stencil_name = svg_stencil_exporter.options.stencil_name
        self.stencil_homepage = svg_stencil_exporter.options.stencil_homepage
        self.stencil_author = svg_stencil_exporter.options.stencil_author
        self.stencil_description = svg_stencil_exporter.options.stencil_description
        self.stencil_license_url = svg_stencil_exporter.options.stencil_license_url

        self.create_github_action = self._str_to_bool(svg_stencil_exporter.options.create_github_action)
        self.create_gitlab_action = self._str_to_bool(svg_stencil_exporter.options.create_gitlab_action)
        self.write_meta = self._str_to_bool(svg_stencil_exporter.options.write_meta)
        self.write_components = self._str_to_bool(svg_stencil_exporter.options.write_components)
        self.create_cover_page = self._str_to_bool(svg_stencil_exporter.options.create_cover_page)
        self.create_readme = self._str_to_bool(svg_stencil_exporter.options.create_readme)

        self.output_path = os.path.normpath(svg_stencil_exporter.options.path)
        self.overwrite_files = self._str_to_bool(svg_stencil_exporter.options.overwrite_files)

        self.use_logging = self._str_to_bool(svg_stencil_exporter.options.use_logging)
        if self.use_logging:
            log_file_name = os.path.join(self.output_path, 'svg_stencil_export.log')

            if os.path.exists(log_file_name):
                logging.basicConfig(filename=log_file_name, filemode="w", level=logging.DEBUG)
            else:
                logging.basicConfig(filename=log_file_name, level=logging.DEBUG)

    def __str__(self):
        toprint =  "EXTENSION PARAMETERS\n"
        toprint += "---------------------------------------\n"
        toprint += "Stencil name:     {}\n".format(self.stencil_name)
        toprint += "Current file:     {}\n".format(self.current_file)
        toprint += "Path:             {}\n".format(self.output_path)
        toprint += "Overwrite files:  {}\n".format(self.overwrite_files)
        toprint += "Use logging:      {}\n".format(self.use_logging)
        toprint += "---------------------------------------\n"
        return toprint

    def _str_to_bool(self, str):
        if str.lower() == 'true':
            return True
        return False

class SVGStencilExporter(inkex.Effect):
    def __init__(self):
        """init the effetc library and get options from gui"""
        inkex.Effect.__init__(self)

        # Controls page
        self.arg_parser.add_argument("--stencil-name", action="store", type=str, dest="stencil_name", default="no-name", help="")
        self.arg_parser.add_argument("--stencil-homepage", action="store", type=str, dest="stencil_homepage", default="", help="")
        self.arg_parser.add_argument("--stencil-author", action="store", type=str, dest="stencil_author", default="", help="")
        self.arg_parser.add_argument("--stencil-description", action="store", type=str, dest="stencil_description", default="", help="")
        self.arg_parser.add_argument("--stencil-license-url", action="store", type=str, dest="stencil_license_url", default="", help="")

        # Controls page
        self.arg_parser.add_argument("--path", action="store", type=str, dest="path", default="", help="export path")
        #self.arg_parser.add_argument("--use-background-layers", action="store", type=str, dest="use_background_layers", default=False, help="")
        self.arg_parser.add_argument("--overwrite-files", action="store", type=str, dest="overwrite_files", default=False, help="")
        self.arg_parser.add_argument("--use-logging", action="store", type=str, dest="use_logging", default=False, help="")

        self.arg_parser.add_argument("--write-meta", action="store", type=str, dest="write_meta", default=False, help="")
        self.arg_parser.add_argument("--write-components", action="store", type=str, dest="write_components", default=False, help="")
        self.arg_parser.add_argument("--create-github-action", action="store", type=str, dest="create_github_action", default=False, help="")
        self.arg_parser.add_argument("--create-gitlab-action", action="store", type=str, dest="create_gitlab_action", default=False, help="")
        self.arg_parser.add_argument("--create-cover-page", action="store", type=str, dest="create_cover_page", default=False, help="")
        self.arg_parser.add_argument("--create-readme", action="store", type=str, dest="create_readme", default=False, help="")


        # HACK - the script is called with a "--tab controls" option as an argument from the notebook param in the inx file.
        # This argument is not used in the script. It's purpose is to suppress an error when the script is called.
        self.arg_parser.add_argument("--tab", action="store", type=str, dest="tab", default="controls", help="")

    def effect(self):

        # Check user options
        options = Options(self)

        # Create the output folder if it doesn't exist
        if not os.path.exists(os.path.join(options.output_path)):
            os.makedirs(os.path.join(options.output_path))

        logging.debug(options)

        components_list = []
        components_data = {}

        # Build the partial inkscape export command
        command = self.build_partial_command(options)

        # Get the layers from the current file
        layers = self.get_layers()

        counter = 0
        # For each layer export a file
        for (layer_id, layer_label, layer_type, parents, translate_x, translate_y) in layers:
            counter += 1
            show_layer_ids = [layer[0] for layer in layers or layer[0] == layer_id]

            # Construct the name of the exported file
            file_name = "{}_{}.{}".format(counter, layer_label, "svg")
            logging.debug("  File name: {}".format(file_name))


            # Create a new file in which we delete unwanted layers to keep the exported file size to a minimum
            logging.debug("  Preparing layer target file [{}]".format(layer_label))
            temporary_file = self.clean_up_target_file(layer_id, show_layer_ids)
            if not temporary_file:
                continue

            # Add to components for json
            components_list.append(file_name)
            # Add to extra componentData for json
            components_data[file_name] = {
                    "type": layer_type,
                    "top": (temporary_file['top'] + self.makeFloat(translate_y)),
                    "bottom": (temporary_file['bottom'] + self.makeFloat(translate_y)),
                    "left": (temporary_file['left'] + self.makeFloat(translate_x)),
                    "right": (temporary_file['right'] + self.makeFloat(translate_x)),
                    "translate_x": self.makeFloat(translate_x),
                    "translate_y": self.makeFloat(translate_y),
                    }

            # Check if the file exists. If not, export it.
            destination_path = os.path.join(options.output_path, file_name)
            if not options.overwrite_files and os.path.exists(destination_path):
                logging.debug("  File already exists: {}\n".format(file_name))

            else:
                logging.debug("  Exporting [{}] as {}".format(layer_label, file_name))
                self.export_to_file(command.copy(), temporary_file["name"], destination_path, options.use_logging)

                # Clean up - delete the temporary file we have created
                os.remove(temporary_file["name"])

        self.delete_temp_elements()
        self.writeComponentsJson(options, components_list, components_data)
        self.writeMetaJson(options)
        self.writeGitHubAction(options)
        self.writeGitlabAction(options)
        self.writeMarkdown(options)
        self.writeHTML(options, components_list)

        logging.debug("===============================\n\nSTENCIL EXPORT FINSISHED:\n")


    def writeComponentsJson(self, options, components_list, components_data):
        if options.write_components:
            destination_comp_json = os.path.join(options.output_path, "stencil-components.json")
            stencil_comp_dict = {
                    "components": components_list,
                    "components_data" : components_data
                    }

            with open(destination_comp_json, 'w') as json_file:
                json.dump(stencil_comp_dict, json_file)


    def writeMetaJson(self, options):
        if options.write_meta:
            destination_meta_json = os.path.join(options.output_path, "stencil-meta.json")
            stencil_meta_dict = {
                    "name": options.stencil_name,
                    "author": options.stencil_author,
                    "description": options.stencil_description,
                    "homepage": options.stencil_homepage,
                    "generator": "SVG Stencil Export - Inkscape Extension - Version 1.4",
                    "license": options.stencil_license_url,
                    }

            with open(destination_meta_json, 'w') as json_file:
                json.dump(stencil_meta_dict, json_file)



    def delete_temp_elements(self):
        temp_elements = self.document.xpath('//svg:path[@inkscape:label="temp_for_stencil_export"]', namespaces=inkex.NSS)
        logging.debug("  temp_elements: [{}]".format(temp_elements))

        for temp_element in temp_elements:
            logging.debug("  delete temp element: [{}]".format(temp_element))
            temp_element.getparent().remove(temp_element)


    def get_layers(self):

        svg_layers = self.document.xpath('//svg:g[@inkscape:groupmode="layer"]', namespaces=inkex.NSS)
        layers = []

        for layer in svg_layers:

            label_attrib_name = "{%s}label" % layer.nsmap['inkscape']
            if label_attrib_name not in layer.attrib:
                continue

            # Skipping hidden layers
            if 'style' in layer.attrib:
                if 'display:none' in layer.attrib['style']:
                    logging.debug("  Skip: [{}]".format(layer.attrib[label_attrib_name]))
                    continue

            ## HANDLE TRANSFORM TRANSLATE
            translate_x = 0.0
            translate_y = 0.0
            if "transform" in layer.attrib:
                if "translate" in layer.attrib["transform"]:
                    translate_x ,translate_y = layer.attrib["transform"].replace("translate","").replace("(","").replace(")","").split(",")
                    logging.debug("  Layer has translate: x[{}] y[{}]".format(translate_x, translate_y))

            # Get layer parents, if any
            parents = []
            parent  = layer.getparent()
            while True:
                if label_attrib_name not in parent.attrib:
                    break
                # Found a parent layer
                # logging.debug("parent: {}".format(parent.attrib["id"]))
                parents.append(parent.attrib["id"])
                parent = parent.getparent()

            #default layer_type
            layer_type = "component"

            # Locked layers get a locked layer_type
            insensitive_name = "{%s}insensitive" % layer.nsmap['sodipodi']
            if insensitive_name in layer.attrib:
                if 'true' in layer.attrib[insensitive_name]:
                    layer_type = "locked"
                    self.draw_start_rect(layer, translate_x, translate_y)

            layer_id = layer.attrib["id"]
            layer_label = layer.attrib[label_attrib_name]

            logging.debug("  Use : [{}, {}]".format(layer_label, layer_type))
            layers.append([layer_id, layer_label, layer_type, parents, translate_x, translate_y])

        logging.debug("  TOTAL NUMBER OF LAYERS: {}\n".format(len(layers)))
        return layers

    def draw_start_rect(self, parent, translate_x, translate_y):
        x1 = 1.0 - self.makeFloat(translate_x)
        y1 = 2.0 - self.makeFloat(translate_y)
        x2 = 1.0 - self.makeFloat(translate_x)
        y2 = 2.0 - self.makeFloat(translate_y)

        line_style   = { 'stroke': '#000000',
                         'stroke-width': str(1),
                         'fill': 'none'
                       }

        line_attribs = {'style' : str(inkex.Style(line_style)),
                        inkex.addNS('label','inkscape') : "temp_for_stencil_export",

                        'd' : 'M '+str(x1) +',' +
                        str(y1) +' L '+str(x2)
                        +','+str(y2) }

        line = etree.SubElement(parent, inkex.addNS('path','svg'), line_attribs )

    def build_partial_command(self, options):
        command = ['inkscape', '--vacuum-defs']
        command.append('--export-plain-svg')
        command.append('--export-type=svg')
        command.append('--export-area-drawing')
        return command

    # Delete unwanted layers to create a clean svg file that will be exported
    def clean_up_target_file(self, target_layer_id, show_layer_ids):
        # Create a copy of the current document
        doc = copy.deepcopy(self.document)
        target_layer_found = False
        target_layer = None

        # Iterate through all layers in the document
        for layer in doc.xpath('//svg:g[@inkscape:groupmode="layer"]', namespaces=inkex.NSS):
            layer_id = layer.attrib["id"]
            layer_label = layer.attrib["{%s}label" % layer.nsmap['inkscape']]

            # Store the target layer
            if not target_layer_found and layer_id == target_layer_id:
                target_layer = layer
                target_layer_found = True

            # Delete all layers
            layer.getparent().remove(layer)
            #logging.debug("    Deleting: [{}, {}]".format(layer_id, layer_label))

        # Add the target layer as the single layer in the document
        # This option is used, only when all the layers are deleted above
        root = doc.getroot()
        if target_layer == None:
            logging.debug("    Error: Target layer not found [{}]".format(show_layer_ids[0]))

        target_layer.attrib['style'] = 'display:inline'
        root.append(target_layer)

        self.mostLeft = 0
        self.mostRight = 0
        self.mostTop = 0
        self.mostBottom = 0

        countChildren = 0
        for node in target_layer.iterchildren():
            countChildren += 1

        if countChildren == 0:
            return False

        for node in target_layer.iterchildren():
            self.analyseNode(node, countChildren)

        # Save the data in a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.svg') as temporary_file:
            tfile = {
                    "name":   temporary_file.name,
                    "left":   self.makeFloat(self.mostLeft),
                    "top":    self.makeFloat(self.mostTop),
                    "right":  self.makeFloat(self.mostRight),
                    "bottom": self.makeFloat(self.mostBottom)
                    }

            logging.debug("    Creating temp file {}".format(temporary_file.name))
            doc.write(temporary_file.name)
            return tfile

    # gather bounding box info to export
    def analyseNode(self, node, countChildren):

        if node.typename == 'TextElement':
            # WORKAROUND FOR A INKSCAPE BBOX BUG
            for tspan in node.xpath('//svg:tspan', namespaces=inkex.NSS):
                node.attrib["x"] = tspan.attrib["x"]
                node.attrib["y"] = tspan.attrib["y"]

                if "x" not in node.attrib or "y" not in node.attrib:
                    logging.debug("REPAIRING MISSING TEXT  X,Y")
                    node.attrib["x"] = tspan.attrib["x"]
                    node.attrib["y"] = tspan.attrib["y"]

                if node.attrib["x"] != tspan.attrib["x"] or node.attrib["y"] != tspan.attrib["y"]:
                    logging.debug("REPAIRING TEXT X,Y, NON EQ WITH TSPAN X,Y")

                    node.attrib["x"] = tspan.attrib["x"]
                    node.attrib["y"] = tspan.attrib["y"]

            if countChildren == 1:
                for tspan in node.xpath('//svg:tspan', namespaces=inkex.NSS):
                    # GET FONT SIZE FOR CHANGING TEXT Y POSITION BASED ON FONT SIZE
                    font_size = "0"

                    if "font-size" in node.attrib:
                        logging.debug("FONT SIZE IN ATTRIB")
                        logging.debug(node.attrib["font-size"])
                        font_size = node.attrib["font-size"].replace("px","")
                    elif "style" in node.attrib and "font-size" in node.attrib["style"]:
                        logging.debug("FONT SIZE IN STYLE")
                        logging.debug(node.attrib["style"].split("font-size")[1].split(";")[0])
                        font_size = node.attrib["style"].split("font-size")[1].split(";")[0].replace(":","").replace("px","")

                    tspan.attrib["y"] = str(self.makeFloat(tspan.attrib["y"]) - self.makeFloat(font_size))
                    break

        bbox = node.shape_box()
        if not bbox:
            return

        logging.debug(['typename',node.typename])
        logging.debug(['shape_box',node.shape_box()])

        left = bbox.left
        top = bbox.top
        width = bbox.width
        height = bbox.height

        if self.mostRight == 0 or (left + width) > self.mostRight:
            self.mostRight = left + width

        if self.mostBottom == 0 or (top + height) > self.mostBottom:
            self.mostBottom = top + height

        if self.mostLeft == 0 or left < self.mostLeft:
            self.mostLeft = left

        if self.mostTop == 0 or top < self.mostTop:
            self.mostTop = top

    def makeFloat(self, var):
        if var is None:
            return 0

        if(type(var) is str):
            arr = var.split(".")
            if(len(arr) > 1):
                var = float(arr[0] +"."+ arr[1])

        return round(float(var),2)

    def export_to_file(self, command, svg_path, output_path, use_logging):
        command.append('--export-filename=%s' % output_path)
        command.append(svg_path)
        logging.debug("    {}\n".format(' '.join(command)))

        try:
            if use_logging:
                # If not piped, stdout and stderr will be showed in an inkscape dialog at the end.
                # Inkscape export will create A LOT of warnings, most of them repeated, and I believe
                # it is pointless to crowd the log file with these warnings.
                with subprocess.Popen(command) as proc:
                    proc.wait(timeout=300)
            else:
                with subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as proc:
                    proc.wait(timeout=300)
        except OSError:
            logging.debug('Error while exporting file {}.'.format(command))
            inkex.errormsg('Error while exporting file {}.'.format(command))
            exit()

    def writeGitHubAction(self, options):
        if options.create_github_action:
            ghdir = os.path.join(options.output_path, ".github", "workflows" )
            os.makedirs( ghdir, exist_ok=True )

            gh_action_yaml = """name: GitHub Pages

on:
  push:
    branches:
      - main  # Set a branch name to trigger deployment

jobs:
  deploy:
    runs-on: ubuntu-20.04
    concurrency:
      group: ${{ github.workflow }}-${{ github.ref }}
    steps:
      - uses: actions/checkout@v3
        with:
          submodules: true  # Fetch Hugo themes (true OR recursive)
          fetch-depth: 0    # Fetch all history for .GitInfo and .Lastmod

      - name: Deploy
        uses: peaceiris/actions-gh-pages@v3
        if: ${{ github.ref == 'refs/heads/main' }}
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: .

"""
            destination_gh_action_yaml = os.path.join(ghdir , "gh-pages.yml")

            ymlfile = open(destination_gh_action_yaml, 'w')
            ymlfile.write(gh_action_yaml)
            ymlfile.close()


    ########################
    ########################

    def writeGitlabAction(self, options):
        if options.create_gitlab_action:
            gl_action_yaml = """pages:
  stage: deploy
  script:
    - mkdir .public
    - cp -r * .public
    - rm -rf public
    - mv .public public
  artifacts:
    paths:
      - public
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
"""
            destination_gl_action_yaml = os.path.join(options.output_path , ".gitlab-ci.yml")

            ymlfile = open(destination_gl_action_yaml, 'w')
            ymlfile.write(gl_action_yaml)
            ymlfile.close()

    ########################
    ########################

    def writeMarkdown(self, options):
        if options.create_readme:
            mddesc = options.stencil_description.replace("\\n","\n")
            indexmd = f"""
# {options.stencil_name}

{mddesc}

Author: {options.stencil_author}

License: {options.stencil_license_url}
"""
            destination_indexmd = os.path.join(options.output_path , "readme.md")

            mdfile = open(destination_indexmd, 'w')
            mdfile.write(indexmd)
            mdfile.close()

    ########################
    ########################

    def writeHTML(self, options, components_list):
        if options.create_cover_page:
            htmldesc = options.stencil_description.replace("\\n","<br>")

            htmljs = '''
  <script>
    switch(window.location.protocol) {
          case 'http:':
          case 'https:':
            document.getElementById('helpText').innerHTML = '<p><a href="https://svg-stencils.github.io/?stencil='+window.location.href+'">preview this stencil in SVG Stencils</a></p><pre style="padding:20px;background-color:#eee; display: inline-block;">{\\n  "name": "'+document.title+'",\\n  "url": "'+window.location.href+'"\\n}</pre><p>Add this stencil to the <a href="https://github.com/svg-stencils/svg-stencils.github.io/edit/main/public/stencils.json">SVG Stencils Library</a> (Only send Pull requests when your Stencil is on a public webserver)</p>'
            break;
            case 'file:':
            document.getElementById('helpText').innerHTML = 'If you run a local webserver you can preview this stencil in <a href="https://svg-stencils.github.io">SVG Stencils</a>. <br>E.g. <strong>cd my-stencil-dir; npm exec http.server -- --cors</strong>'
            break;
            default:
            document.getElementById('helpText').innerHTML = ''
            }
  </script>
        '''

            compstr=""
            for comp in components_list:
                compstr=compstr+'<div class="col-sm"> <img style="max-width:200px;" class="img-thumbnail" src="'+comp+'" /></div>'

            indexhtml = f"""<html>
  <head>
    <title>{options.stencil_name}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-1BmE4kWBq78iYhFldvKuhfTAU6auU8tT94WrHftjDbrCEXSU1oBoqyl2QvZ6jIW3" crossorigin="anonymous">
  </head>
  <body>
    <div class="container">
      <div class="row m-3">
        <h1>{options.stencil_name}</h1>
        <p>
            Author: {options.stencil_author}<br/>
            <a href="{options.stencil_license_url}">License</a>
        </p>
        <p>{htmldesc}</p>
        <div id="helpText"></div>
      </div>
      <hr>
      <div class="row m-3">
          {compstr}
      </div>
    </div>
    {htmljs}
  </body>
</html>
"""
            destination_indexhtml = os.path.join(options.output_path , "index.html")

            htmlfile = open(destination_indexhtml, 'w')
            htmlfile.write(indexhtml)
            htmlfile.close()

def _main():
    exporter = SVGStencilExporter()
    exporter.run()
    exit()

if __name__ == "__main__":
    _main()
