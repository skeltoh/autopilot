import sys
import os
import json
from collections import OrderedDict as odict
from PySide import QtCore
from PySide import QtGui
sys.path.append('/home/jonny/git/RPilot')
from core.terminal import New_Mouse_Wizard
from core.mouse import Mouse

class Control_Panel(QtGui.QWidget):
    # Hosts two nested tab widgets to select pilot and mouse,
    # set params, run mice, etc.

    def __init__(self, pilots=None, pilot_width=30, mouse_width=150, prefs=None):
        super(Control_Panel, self).__init__()
        # We should be passed a pilot odict {'pilot':[mouse1, mouse2]}
        # If we're not, try to load prefs, and if we don't have prefs, from default loc.

        self.prefs = prefs

        if pilots:
            self.pilots = pilots
        else:
            try:
                with open(self.prefs['PILOT_DB']) as pilot_file:
                    self.pilots = json.load(pilot_file, object_pairs_hook=odict)
            except NameError:
                try:
                    with open('/usr/rpilot/pilot_db.json') as pilot_file:
                        self.pilots = json.load(pilot_file, object_pairs_hook=odict)
                except IOError:
                    Exception('Couldnt find pilot directory!')

        # Sizes to pass to the tab widgets
        self.pilot_width = pilot_width
        self.mouse_width = mouse_width

        # Keep a dict of the ids and Mouse objects that are currently running
        self.running_mice = {}

        self.init_ui()

    def init_ui(self):
        # Layout for whole widget
        self.layout = QtGui.QVBoxLayout()
        self.layout.setContentsMargins(0,0,0,0)
        self.setLayout(self.layout)

        # Make top row 'new' buttons
        new_button_panel = QtGui.QHBoxLayout()
        new_button_panel.setContentsMargins(0,0,0,0)
        self.new_pilot_button = QtGui.QPushButton('+')
        self.new_pilot_button.setFixedSize(self.pilot_width, self.pilot_width)
        self.new_pilot_button.clicked.connect(self.create_pilot)
        self.new_mouse_button = QtGui.QPushButton('+')
        self.new_mouse_button.setFixedSize(self.mouse_width, self.pilot_width)
        self.new_mouse_button.clicked.connect(self.create_mouse)
        new_button_panel.addWidget(self.new_pilot_button)
        new_button_panel.addWidget(self.new_mouse_button)
        self.layout.addLayout(new_button_panel)

        # Make main pilot tab widget
        self.pilot_tabs = QtGui.QTabWidget()
        # NOTE! If you make the "new pilot" button bigger than 30x30px,
        # You must pass the vertical size to Expanding tabs or.. well you'll see.
        self.pilot_tabs.setTabBar(Expanding_Tabs(self.pilot_width))
        self.pilot_tabs.setUsesScrollButtons(False)
        self.pilot_tabs.setTabPosition(QtGui.QTabWidget.West)

        self.layout.addWidget(self.pilot_tabs)

        # Make dict to store handles to mice tabs
        self.mouse_tabs = {}

        self.populate_tabs()


    def populate_tabs(self):
        # Clear tabs if there are any
        # We can use clear even though it doesn't delete the sub-widgets because
        # adding a bunch of mice should be rare,
        # and the widgets themselves should be lightweight
        self.pilot_tabs.clear()

        # Iterate through pilots and mice, making tabs and subtabs
        for pilot, mice in self.pilots.items():
            mice_tabs = QtGui.QTabWidget()
            mice_tabs.setTabBar(Stacked_Tabs(width=self.mouse_width,
                                             height=self.pilot_width))
            mice_tabs.setTabPosition(QtGui.QTabWidget.West)
            for m in mice:
                param_widget = Parameters()
                mice_tabs.addTab(param_widget, m)
            mice_tabs.currentChanged.connect(self.select_mouse)


            self.pilot_tabs.addTab(mice_tabs, pilot)
        self.pilot_tabs.currentChanged.connect(self.select_pilot)

    def create_pilot(self):
        name, ok = QtGui.QInputDialog.getText(self, "Pilot ID", "Pilot ID:")
        if ok and name != '':
            self.pilots[name] = []
            self.update_db()
            # Make a mouse TabWidget
            mice_tabs = QtGui.QTabWidget()
            mice_tabs.setTabBar(Stacked_Tabs(width=self.mouse_width,
                                             height=self.pilot_width))
            mice_tabs.setTabPosition(QtGui.QTabWidget.West)
            mice_tabs.currentChanged.connect(self.select_mouse)
            self.pilot_tabs.addTab(mice_tabs,name)
            # TODO: Add a row to the dataview

        else:
            # Idk maybe pop a dialog window but i don't really see why
            pass

    def create_mouse(self):
        new_mouse_wizard = New_Mouse_Wizard(self.prefs['PROTOCOLDIR'])
        new_mouse_wizard.exec_()

        # If the wizard completed successfully, get its values
        if new_mouse_wizard.result() == 1:
            biography_vals = new_mouse_wizard.bio_tab.values

            # Make a new mouse object, make it temporary because we want to close it
            mouse_obj = Mouse(biography_vals['id'], new=True,
                              biography=biography_vals)

            # If a protocol was selected in the mouse wizard, assign it.
            try:
                protocol_vals = new_mouse_wizard.task_tab.values
                if 'protocol' in protocol_vals.keys() and 'step' in protocol_vals.keys():
                    protocol_file = os.path.join(prefs['PROTOCOLDIR'], protocol_vals['protocol'] + '.json')
                    mouse_obj.assign_protocol(protocol_file, int(protocol_vals['step']))
            except:
                # the wizard couldn't find the protocol dir, so no task tab was made
                pass


            # Close the file because we want to keep mouse objects only when they are running
            mouse_obj.close_h5f()

            # Add mouse to pilots dict, update it and our tabs
            current_pilot = self.pilot_tabs.tabText(self.pilot_tabs.currentIndex())
            self.pilots[current_pilot].append(biography_vals['id'])
            self.update_db()
            self.populate_tabs()




    def select_pilot(self):
        # Probably just ping it to check its status
        pass

    def select_mouse(self, index):
        # When a mouse's button is clicked, we expand a parameters pane for it
        # This pane lets us give the mouse a protocol if it doesn't have one,
        # adjust the parameters if it does, and start the mouse running

        # sender is the qtabwidget, we we get the text of the current tab
        sender = self.sender()
        mouse_id = sender.tabText(index)

        # open the mouse object if it isn't already
        if not mouse_id in self.running_mice.keys():
            mouse_obj = Mouse(mouse_id)
        else:
            mouse_obj = self.running_mice[mouse_id]

        # TODO: START HERE NEXT TIME


        params_widget = sender.widget(index)
        params_widget.show_params(mouse_id)

        #sender = sender.checkedButton()
        #self.mouse = sender.text()

    def update_db(self):
        # TODO: Pretty hacky, should explicitly pass prefs or find some way of making sure every object has it
        try:
            with open(prefs['PILOT_DB'], 'w') as pilot_file:
                json.dump(self.pilots, pilot_file)
        except NameError:
            try:
                with open('/usr/rpilot/pilot_db.json') as pilot_file:
                    self.pilots = json.load(pilot_file, object_pairs_hook=odict)
            except IOError:
                Exception('Couldnt update pilot db!')
                # TODO: Probably just pop a dialog, don't need to crash shit.





        # Add corner widget to declare new pilot
        #self.new_pilot_button = QtGui.QPushButton('+')
        #self.new_pilot_button.setFixedHeight(30)
        #self.pilot_tabs.setCornerWidget(self.new_pilot_button, QtCore.Qt.BottomLeftCorner)




# def expanding_tabs:
#     tabs = QtGui.QTabBar()
#     tabs.setExpanding(True)
#     layout = QtGui.QVBoxLayout()
#         self.setLayout(layout)
#         stackedLayout = QtGui.QStackedLayout()
#         layout.addWidget(self)
#         layout.addLayout(stackedLayout)

class Expanding_Tabs(QtGui.QTabBar):
    # The expanding method of the QTabBar doesn't work,
    # we have to manually adjust the size policy and size hint
    def __init__(self, width=30):
        super(Expanding_Tabs, self).__init__()
        self.setSizePolicy(QtGui.QSizePolicy.Policy.Fixed, QtGui.QSizePolicy.Policy.Minimum)
        self.width = width

    def tabSizeHint(self, index):
        # Pretty janky, but the tab bar is two children deep from the main widget
        # First compute the size taken up by the 'new' button and the margin
        # We assume the code is unchanged that binds our width to that button's width
        ctl_panel_handle = self.parent().parent()
        margins = ctl_panel_handle.layout.getContentsMargins()
        nudge_size = self.width + margins[1] + margins[3] + ctl_panel_handle.layout.spacing() # top and bottom
        return QtCore.QSize(self.width, (ctl_panel_handle.frameGeometry().height()-nudge_size)/self.count())


class Stacked_Tabs(QtGui.QTabBar):
    # Setting tab position to west also rotates text 90 degrees, which is dumb
    # From https://stackoverflow.com/questions/3607709/how-to-change-text-alignment-in-qtabwidget
    def __init__(self, width=150, height=30):
        super(Stacked_Tabs, self).__init__()
        self.tabSize = QtCore.QSize(width, height)

    def paintEvent(self, event):
        painter = QtGui.QStylePainter(self)
        option = QtGui.QStyleOptionTab()

        #painter.begin(self)
        for index in range(self.count()):
            self.initStyleOption(option, index)
            tabRect = self.tabRect(index)
            tabRect.moveLeft(10)
            painter.drawControl(QtGui.QStyle.CE_TabBarTabShape, option)
            painter.drawText(tabRect, QtCore.Qt.AlignVCenter | QtCore.Qt.TextDontClip,
                             self.tabText(index))

        painter.end()

    def tabSizeHint(self, index):
        return self.tabSize


class Test_App(QtGui.QWidget):
    def __init__(self, prefs):
        super(Test_App, self).__init__()
        self.prefs = prefs
        self.initUI()

    def initUI(self):
        #self.setWindowState(QtCore.Qt.WindowMaximized)
        self.layout = QtGui.QHBoxLayout()
        self.setLayout(self.layout)
        self.panel = Control_Panel(prefs=self.prefs)
        self.layout.addWidget(self.panel)
        self.layout.addStretch(1)
        titleBarHeight = self.style().pixelMetric(QtGui.QStyle.PM_TitleBarHeight,
            QtGui.QStyleOptionTitleBar(), self)
        winsize = app.desktop().availableGeometry()
        # Then subtract height of titlebar
        winsize.setHeight(winsize.height()-titleBarHeight*2)
        self.setGeometry(winsize)

        #self.show()






class Parameters(QtGui.QWidget):
    # Reads and edits tasks parameters from a mouse's protocol
    def __init__(self):
        super(Parameters, self).__init__()

        # We want to do essentially nothing on init and only populate params when asked to



if __name__ == '__main__':
    prefs_file = '/usr/rpilot/prefs.json'
    with open(prefs_file) as prefs_file_open:
        prefs = json.load(prefs_file_open)

    app = QtGui.QApplication(sys.argv)
    app.setStyle('Cleanlooks')
    ex = Test_App(prefs)
    ex.show()
    sys.exit(app.exec_())





