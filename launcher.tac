# Run me as "twistd -ny launcher.tac"

import os, sys
sys.path = [os.path.join(os.getcwd(), 'conf'),] + sys.path

import stratum
application = stratum.setup()

import services
