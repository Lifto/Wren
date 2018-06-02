Wren
====

Experiments in scored-text UI

This code contains snippets cut and pasted from
https://github.com/facebookresearch/poincare-embeddings
by Facebook Research, used under
https://creativecommons.org/licenses/by-nc/4.0/

Notes on this Work-in-Progress
------------------------------

This is a work-in-progress that is being put down for a while. In this most
recent incarnation you can import the terms related to 'mammal' from WordNet,
and see the score relationships between the terms. The scores are based on the
hyperbolic distance as computed using the Facebook Research poincare-embeddings
 code.

Otherwise, Wren is intended to be a user interface for constructing and viewing
 an understanding-structure based on comparisons between individual multimedia
 elements. Intended to be used in a loop that includes a user who reviews
 element-comparisons and adds new elements and comparators.

Demo
----

Install the packages for requirements.txt, then run wren.py in Python 3.6 or
later.

Wren will open with a blank screen (note Wren is presently broken if you write
anything in the Clips that does not appear exactly in the mammals word set!)

Click on the 'Import Mammals Closure' in the tool bar and watch the progress
bar as the mammals are imported. Once they are you can examine them with the
cursor keys. Note the numbers in each Clip, the left (red) number is the
hyperbolic distance from the cursor's Clip to the top Clip (home Clip)

Place the Cursor over a Clip that is not the top Clip and press command-Enter,
or use the mouse to click 'Ranked Column' from the toolbar at the top. Watch
progress bars for a while and then notice there is now a second column with the
 Cursor's Clip at the top. Everything below that clip is sorted by hyperbolic
 distance from the top Clip.

 If you exit Wren and open it again you will not need to re-import, state is
 saved in wren_temp.db. (delete wren_temp.db to start over.)

Usage
-----

(some of these seemed to have stopped working when I started using PyQT5
Actions)

arrow keys: move Selection (red)

shift arrow keys: move the Marker (blue)

enter: create/edit Clip in Selection's grid square. (Edit happens in Inspector)

esc: cease editing Clip, return focus to Grid.

ctrl p: mark the selection as the child of the marker

ctrl i: open a dialog to import Datums (try it on documents/tensors.txt)
    (it is slow and could use a progress bar.) (broken)

ctrl backspace: delete Clip at Selection's grid square (not the Datum, just the
    Clip.)

ctrl delete: archive Clip's Datum, delete all Clips holding that Datum,
    Datum will not appear in further results.

ctrl w: delete Column at Selection's grid square

ctrl c, x and v: Cut, Copy and Paste Clip (in Grid Cursor mode)

ctrl arrow keys: scroll

ctrl d: scroll so Selection's Clip is at center-left

ctrl f: scroll so Selection's Clip is at center

ctrl g: scroll so Selection's Clip is at right

ctrl l: cycles between scrolling to the Selection's column head, tail or
homerow.

ctrl enter: Insert a column to the right of the Selection, make copy Clips for
Datums that have a score relative to the Selection's Clip's Datum in order
top-to-bottom. 20 Clips are added to the Grid, with un-related Clips padding
 out the results. (note this is under experiment now and is changing, it's
 not a column at the moment.)

ctrl r: re-sort current column based on current scores

ctrl t: Insert a column at Selection, push Selection's column to the left.

When the both Selection and Marker are on the same Clip you may type in a
number which is the score relating the selection's Clip's Datum to the
Marker's Clip's Datum.

ctrl a: Import the Tensor Algebra notes

Installation
------------

Install git from https://git-scm.com/book/en/v2/Getting-Started-Installing-Git

In the directory where you want to install the Wren directory
git clone git@github.com:jfries/wren.git

Install Python3 from python.org (this installs pip and pip3)

pip install virtualenv
pip install virtualenvwrapper

Add this to your .profile
# set where virutal environments will live
export WORKON_HOME=~/Documents/Development/.virtualenvs
# ensure all new environments are isolated from the site-packages directory
export VIRTUALENVWRAPPER_VIRTUALENV_ARGS='--no-site-packages'
# use the same directory for virtualenvs as virtualenvwrapper
export PIP_VIRTUALENV_BASE=$WORKON_HOME
# makes pip detect an active virtualenv and install to it
export PIP_RESPECT_VIRTUALENV=true
if [[ -r /Library/Frameworks/Python.framework/Versions/2.7/bin/virtualenvwrapper.sh ]]; then
    source /Library/Frameworks/Python.framework/Versions/2.7/bin/virtualenvwrapper.sh
else
    echo "WARNING: Can't find virtualenvwrapper.sh"
fi

mkvirtualenv --python=/Library/Frameworks/Python.framework/Versions/3.6/bin/python3 wren
pip3 install -r requirements.txt

If you get this issue with matplotlib:
RuntimeError: Python is not installed as a framework.
do this:
cd ~/.matplotlib
nano matplotlibrc
put this in the file:
backend: TkAgg

Database
--------

Wren makes a wren_temp.db in its working directory. Delete it or move it or
rename it and Wren'll start over by making a new wren_temp.db.
