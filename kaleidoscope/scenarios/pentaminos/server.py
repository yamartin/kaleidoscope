from os.path import dirname, join
from kaleidoscope.scenario import KalScenarioServer
from time import time
from penta_color import penta_schemes
from penta_common import PentaListContainer

from kivy.uix.widget import Widget
from kivy.core.image import Image
from kivy.utils import get_color_from_hex
from kivy.core.window import Window
from kivy.graphics import Color, BorderImage, Rectangle

TIMER = 60 * 2
PENTAMINOS_SIZE = 5, 3
PENTAMINOS_SIZE2 = 6, 5
PENTAMINOS_COUNT_BY_USERS = 3

background = Image(join(dirname(__file__), 'background.png'))
background.texture.wrap = 'repeat'
btnbg = Image(join(dirname(__file__), 'buttonbackground.png')).texture

class Pentaminos(KalScenarioServer):
    resources = (
        'penta-background.png',
        'penta-background-bottom.png',
        'penta-square.png',
        'penta-square-shadow.png',
        'background.png',
        'client.py',
        'penta_color.py',
        'pentaminos.kv',
        'penta_common.py'
    )
    def __init__(self, *largs):
        super(Pentaminos, self).__init__(*largs)
        self.timeout = 0
        self.timemsg = 0
        self.c1 = get_color_from_hex('#96be25aa')
        self.c2 = get_color_from_hex('#e6461faa')
        self.c3 = get_color_from_hex('#81cac8aa')
        self.c4 = get_color_from_hex('#7f398baa')
        self.players = {}

        # init client table
        for client in self.controler.clients:
            self.players[client] = {
                'client': client,
                'name': self.controler.get_client_name(client),
                'ready': False,
                'done': False,
                'place': self.controler.metadata[client]['place'],
                'pentaminos': []
            }

        self.init_ui()

    def init_ui(self):
        self.pentalist = PentaListContainer(server=True)
        self.controler.app.show(self.pentalist)
        self.build_canvas(self.pentalist.canvas)

    def build_canvas(self, canvas):
        places = [player['place'] for player in self.players.itervalues()]
        canvas.before.clear()
        with canvas.before:
            Color(1, 1, 1)
            cx, cy = Window.center
            m = 50
            m2 = m * 2
            if 1 in places:
                Color(*self.c1)
                BorderImage(texture=btnbg, pos=(m, m), size=(cx - m2, cy - m2), radius=15)
            if 2 in places:
                Color(*self.c2)
                BorderImage(texture=btnbg, pos=(cx + m, m), size=(cx - m2, cy - m2), radius=15)
            if 3 in places:
                Color(*self.c3)
                BorderImage(texture=btnbg, pos=(m, cy + m), size=(cx - m2, cy - m2), radius=15)
            if 4 in places:
                Color(*self.c4)
                BorderImage(texture=btnbg, pos=(cx + m, cy + m), size=(cx - m2, cy - m2), radius=15)


    def client_login(self, client):
        self.players[client]['ready'] = True

    def client_logout(self, client):
        del self.players[client]
        if hasattr(self, 'root_game2'):
            self.build_canvas(self.root_game2)
        else:
            self.build_canvas(self.pentalist.canvas)

    def start(self):
        '''Scenario start, wait for all player to be ready
        '''
        super(Pentaminos, self).start()
        self.send_all('WAITREADY')
        self.state = 'waitready'

    #
    # Client commands received
    # do_client_<command>(client, [...])
    #

    def do_client_pentamino(self, client, args):
        if len(args) != 4:
            self.send_to(client, 'ERROR invalid command\n')
            return
        key, w, h, penta = args
        w, h = map(int, (w, h))
        place = self.players[client]['place']
        color = getattr(self, 'c%d' % place)
        if self.pentalist.add_penta(key, penta, w, h, color=color) is False:
            self.send_to(client, 'CANCEL %s' % key)
            self.send_to(client, 'GIVE 5')
            self.send_to(client, 'MSG Le pentaminos existe, trouve en un autre !')
            return
        print '# Add pentamino %s from %s to the list' % (key, client.addr)
        self.players[client]['pentaminos'].append((key, w, h, penta))
        left = PENTAMINOS_COUNT_BY_USERS - len(self.players[client]['pentaminos'])
        if left:
            # validate to client
            self.send_to(client, 'GIVE 5')
            self.send_to(client, 'MSG Bravo ! Encore %d pentaminos.' % left)
        else:
            self.send_to(client, 'MSG Tu as fini ! Attends tes camarades maintenant')

    def do_client_ready(self, client, args):
        self.players[client]['ready'] = True
        count = len([x for x in self.players.itervalues() if not x['ready']])
        if count:
            self.msg_all('@%s ok, en attente de %d joueur(s)' % (
                self.players[client]['name'], count))

    def do_client_rectdone(self, client, args):
        self.players[client]['done'] = True
        self.send_to(client, 'ENDING')
        self.msg_all('@%s a fini son rectangle !' % self.players[client]['name'])

    #
    # State machine
    #

    def run_waitready(self):
        '''Wait for all player to be ready
        '''
        ready = True
        for player in self.players.itervalues():
            ready = ready and player['ready']
        if not ready:
            return

        self.timeout = time() + TIMER
        self.msg_all('Construis %d pentaminos' % PENTAMINOS_COUNT_BY_USERS)
        self.send_all('TIME %d' % int(self.timeout))
        self.send_all('SIZE %d %d' % PENTAMINOS_SIZE)
        self.send_all('GAME1')
        self.send_all('GIVE 5')
        self.state = 'game1'
        self.pentaminos = []

    def run_game1(self):
        '''Game is running
        '''
        if time() > self.timeout:
            self.state = 'reset_for_game2'
            return
        done = True
        for player in self.players.itervalues():
            if len(player['pentaminos']) != PENTAMINOS_COUNT_BY_USERS:
                done = False
        if done:
            self.msg_all('Tout le monde a fini, on commence la seconde partie..')
            self.state = 'game1_wait'
            self.timeout = time() + 2
            self.send_all('TIME %d' % int(self.timeout))

    def run_game1_wait(self):
        if time() > self.timeout:
            self.state = 'reset_for_game2'

    def run_reset_for_game2(self):
        self.root_game2 = w = Widget()
        self.build_canvas(w.canvas)
        self.controler.app.show(w)
        self.send_all('CLEAR')
        self.msg_all('Remplis le rectangle avec les pentaminos')
        self.state = 'game2'

        # extract all pentaminos
        pentas = []
        for player in self.players.itervalues():
            for penta in player['pentaminos']:
                pentas.append((penta, player))

        # do game 2
        self.send_all('GAME2')
        self.send_all('SIZE %d %d' % PENTAMINOS_SIZE2)

        # distribute
        for k, v in penta_schemes.iteritems():
            size, string = v[0]
            w, h = size
            # send the penta to the user
            self.send_all('PENTA %s %d %d %s' % (
                k, w, h, string))

        self.timeout = time() + TIMER
        self.send_all('TIME %d' % int(self.timeout))

    def run_game2(self):
        if time() > self.timeout:
            self.msg_all('Fin du jeu !')
            self.state = 'game3'
            self.timeout = time() + 5
            self.send_all('TIME %d' % int(self.timeout))
            return

        done = True
        for player in self.players.itervalues():
            if not player['done']:
                done = False
        if done:
            self.msg_all('Bravo, tout le monde a fini !')
            self.state = 'game3'
            self.timeout = time() + 5
            self.send_all('TIME %d' % int(self.timeout))

    def run_game3(self):
        if time() < self.timeout:
            return
        self.controler.switch_scenario('choose')
        self.controler.load_all()

scenario_class = Pentaminos
