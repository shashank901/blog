from fabric.api import *
import fabric.contrib.project as project
import os
import re
import sys
import datetime

from pelicanconf import ARTICLE_DIR, DEFAULT_CATEGORY, AUTHOR, OUTPUT_PATH, THEME, THEME_BRANCH, PLUGIN_PATH, PLUGIN_BRANCH

# Local path configuration (can be absolute or relative to fabfile)
env.deploy_path = 'output'
DEPLOY_PATH = env.deploy_path

# Remote server configuration
production = 'root@localhost:22'
dest_path = '/var/www'

# Rackspace Cloud Files configuration settings
env.cloudfiles_username = 'my_rackspace_username'
env.cloudfiles_api_key = 'my_rackspace_api_key'
env.cloudfiles_container = 'my_cloudfiles_container'

def prebuild():
    """ tasks to run before any file generation - build, preview, publish, etc. """
    # check for themes
    if not os.path.exists(THEME):
        print("ERROR: theme directory %s does not exist." % THEME)
        sys.exit(1)
    branch = local("cd %s && git rev-parse --abbrev-ref HEAD" % THEME, capture=True).strip()
    if branch != THEME_BRANCH:
        print("ERROR: %s is on wrong branch (%s not %s)" % (THEME, branch, THEME_BRANCH))
        sys.exit(1)
    # check for plugins
    if not os.path.exists(os.path.join(PLUGIN_PATH, 'LICENSE')):
        print("ERROR: plugin directory %s does not exist." % PLUGIN_PATH)
        sys.exit(1)
    branch = local("cd %s && git rev-parse --abbrev-ref HEAD" % PLUGIN_PATH, capture=True).strip()
    if branch != PLUGIN_BRANCH:
        print("ERROR: %s is on wrong branch (%s not %s)" % (PLUGIN_PATH, branch, PLUGIN_BRANCH))
        sys.exit(1)

def clean():
    """ remove DEPLOY_PATH if it exists, then recreate """
    if os.path.isdir(DEPLOY_PATH):
        local('rm -rf {deploy_path}'.format(**env))
        local('mkdir {deploy_path}'.format(**env))

def build():
    """ run pelican to build output """
    prebuild()
    local('pelican -s pelicanconf.py')

def rebuild():
    """ clean and build """
    clean()
    build()

def regenerate():
    """ pelican -r ; regenerate whenever a file changes """
    prebuild()
    local('pelican -r -s pelicanconf.py')

def serve():
    """ SimpleHTTPServer """
    local('cd {deploy_path} && python -m SimpleHTTPServer'.format(**env))

def reserve():
    """ build and serve """
    build()
    serve()

def preview():
    """ pelican with publishconf.py """
    prebuild()
    local('pelican -s publishconf.py')

def publish():
    """ rebuild and publish to GH pages """
    resp = prompt("This will clean, build, and push to GH pages. Ok? [yes|No]")
    if not re.match(r'(y|Y|yes|Yes|YES)', resp):
        return False
    clean()
    preview()
    local("ghp-import %s" % OUTPUT_PATH)
    local("git push origin gh-pages")

def _make_slug(title):
    """ make a slug from the given title """
    slug = title.lower()
    slug = re.sub('\s+', '-', slug)
    slug = re.sub(r'[^A-Za-z0-9_-]', '', slug)
    return slug

def _prompt_title():
    """ prompt for a post title """
    confirm = 'no'
    while not re.match(r'(y|Y|yes|Yes|YES)', confirm):
        title = prompt("Post Title:")
        print("")
        print("Post Title: '%s'" % title)
        print("Slug: '%s'" % _make_slug(title))
        print("")
        confirm = prompt("Is this correct? [y|N]", default='no')
    return title

def drafts():
    """ list drafts """
    local('grep -rl -e "^Status: draft" -e "^:status: draft" content/ | grep -v "~$"')

def _prompt_category(cats):
    """ prompt for a category selection """
    print("\n\nSelect a Category:\n==================")
    for c in xrange(0, len(cats)):
        print("%d) %s" % (c, cats[c]))
    print("")
    confirm = 'no'
    while not re.match(r'(y|Y|yes|Yes|YES)', confirm):
        category = prompt("Category (number or free text):")
        print("")
        if re.match(r'[0-9]+', category):
            foo = int(category)
            if foo in xrange(0, len(cats)):
                category = cats[foo]
            else:
                print("Invalid number.")
                continue
        print("Category: '%s'" % category)
        print("")
        confirm = prompt("Is this correct? [y|N]", default='no')
    return category

def post():
    """ write a post """
    cats = _get_categories()
    title = _prompt_title()
    category = _prompt_category(cats)
    dt = datetime.datetime.now()
    dname = os.path.join(ARTICLE_DIR, dt.strftime('%Y'), dt.strftime('%m'))
    if not os.path.exists(dname):
        os.makedirs(dname)
    slug = _make_slug(title)
    fname = "%s.md" % slug
    fpath = os.path.join(dname, fname)
    datestr = dt.strftime('%Y-%m-%d %H:%M')
    metadata = """Title: {title}
Date: {datestr}
Author: {author}
Category: {category}
Tags: 
Slug: {slug}
Summary: <<<<< summary goes here >>>>>>>
Status: draft

content (written in MarkDown - http://daringfireball.net/projects/markdown/syntax )
""".format(title=title,
           datestr=datestr,
           category=category,
           slug=slug,
           author=AUTHOR)
    with open(fpath, 'w') as fh:
        fh.write(metadata)
        # need to flush and fsync before an exec
        fh.flush()
        os.fsync(fh.fileno())
    if os.environ.get('EDITOR') is None:
        print("EDITOR not defined. Your post is started at: %s" % fpath)
    else:
        editor = os.environ.get('EDITOR')
        print("Replacing fab process with: %s %s" % (editor, os.path.abspath(fpath)))
        # replace our process with the editor...
        os.execlp(editor, os.path.basename(editor), os.path.abspath(fpath))

def _get_categories():
    """ return a list of all categories in current posts """
    lines = local('grep -rh "^Category: " %s/ | sort | uniq' % ARTICLE_DIR, capture=True)
    cats = []
    cat_re = re.compile(r'^Category: (.+)$')
    for l in str(lines).split("\n"):
        m = cat_re.match(l)
        if not m:
            continue
        cats.append(m.group(1))
    return cats

def categories():
    """ show all current blog post categories """
    for c in _get_categories():
        print c
