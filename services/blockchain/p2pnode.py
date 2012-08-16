from twisted.internet import reactor, defer
from twisted.internet.protocol import ReconnectingClientFactory
import StringIO
import binascii

import stratum.logger
log = stratum.logger.get_logger('p2pnode')

try:
    # Provide deserialization for Bitcoin transactions
    import Abe.deserialize
    is_Abe = True
except ImportError:
    print "Abe not installed, some extended features won't be available"
    is_Abe = False

import halfnode

'''
This is wrapper around generic Halfnode implementation.

Features:
  * Keep one open P2P connection to trusted Bitcoin node
  * Provide broadcast_tx method for broadcasting new transactions
'''

# Instance of BitcoinP2PProtocol connected to trusted Bitcoin node
_connection = None
_alternate_connection = None

def get_connection():
    if not _connection:
        raise Exception("Trusted node not connected")
    return _connection

def get_alternate_connection():
    if not _alternate_connection:
        raise Exception("Alternate node not connected")
    return _alternate_connection


class AlternateP2PProtocol(halfnode.BitcoinP2PProtocol):
    def __init__(self):
        self.txhashes = {}
        
    def connectionMade(self):
        halfnode.BitcoinP2PProtocol.connectionMade(self)
        log.info("Alternate P2P connected")

        global _alternate_connection
        _alternate_connection = self

        reactor.callLater(10, self.ping)
        
    def observe_tx(self, txhash, timeout):
        print "OBSERVING", txhash
        d = defer.Deferred()
        t = reactor.callLater(timeout, self._timeout, txhash)
        self.txhashes[txhash] = (d, t)
        
        return d
        
    def _observed(self, txhash):
        '''txhash has been found on Bitcoin network'''
        if txhash not in self.txhashes:
            return

        print "OBSERVED", txhash
        
        # defer and timer
        (d, t) = self.txhashes[txhash]        
        del self.txhashes[txhash]
        
        t.cancel()
        d.callback(txhash)
        
    def _timeout(self, txhash):
        '''txhash hasn't been observed on Bitcoin network, cancel observation'''
        print "TIMEOUTED", txhash
        
        if txhash not in self.txhashes:
            return
        
        (d, t) = self.txhashes[txhash]
        del self.txhashes[txhash]
        
        d.errback(txhash)

    def do_tx(self, message):
        txhash = "%x" % message.tx.calc_sha256()
        #print "NEW TX", txhash
        self._observed(txhash)        
        
    def connectionLost(self, reason):
        halfnode.BitcoinP2PProtocol.connectionLost(self, reason)
        log.info("Alternate P2P disconnected")

        global _alternate_connection
        _alternate_connection = None

    def ping(self):
        self.send_message(halfnode.msg_ping())
        reactor.callLater(300, self.ping)
    
class MainP2PProtocol(halfnode.BitcoinP2PProtocol):
    def connectionMade(self):
        halfnode.BitcoinP2PProtocol.connectionMade(self)
        log.info("P2P connected")

        global _connection
        _connection = self

        reactor.callLater(10, self.ping)
                
    def connectionLost(self, reason):
        halfnode.BitcoinP2PProtocol.connectionLost(self, reason)
        log.info("P2P disconnected")

        global _connection
        _connection = None

    def ping(self):
        self.send_message(halfnode.msg_ping())
        reactor.callLater(300, self.ping)

    def do_inv(self, message):
        want = halfnode.msg_getdata()
        for i in message.inv:
            if i.type == 1:
                # Transaction
                
                # TODO: Lookup to Abe if we already have such tx
                
                want.inv.append(i)

            elif i.type == 2:
                # Block
                
                # TODO: Lookup to Abe if we already have such block
                
                want.inv.append(i)
        
        if not len(want.inv):
            return
        
        self.send_message(want)
                
    def broadcast_tx(self, txdata):
        '''Broadcast new transaction (as a hex stream) to trusted node'''
        tx = halfnode.msg_tx()
        tx.deserialize(StringIO.StringIO(binascii.unhexlify(txdata)))
        
        alternate = get_alternate_connection()
        d = alternate.observe_tx("%x" % tx.tx.calc_sha256(), 5)

        self.send_message(tx)
        
        # Defer will throw confirm when alternate connection
        # confirm that tx has been broadcasted or errback on timeouts
        return d
        
    def do_block(self, message):
        '''Process incoming Bitcoin block'''      
        if not is_Abe:
            # Abe is not installed, parsing transactions is not available
            return
        
        print 'xxx', message.block.calc_sha256()
        #print message.block.serialize()
        
        # TODO: Push to Abe
        
    def do_tx(self, message):
        '''Process incoming Bitcoin transaction'''      
        if not is_Abe:
            # Abe is not installed, parsing transactions is not available
            return
        
        #print message.tx.serialize()
        
        # TODO: Push to Abe
        
        '''
        message.tx.calc_sha256()
                
        for intx in message.tx.vin:
            pubkey = Abe.deserialize.extract_public_key(intx.scriptSig)
            if pubkey == '(None)':
                pubkey = None
                
            log.debug('in %s' % pubkey) 
            #print intx.prevout.n, intx.prevout.hash

        for outtx in message.tx.vout:
            pubkey = Abe.deserialize.extract_public_key(outtx.scriptPubKey)
            if pubkey == '(None)':
                pubkey = None

            log.debug('out %s %f' % (pubkey, outtx.nValue / 10**8.))
            
        log.debug('---')
        #pubkey = binascii.hexlify(message.tx.vout[0].scriptPubKey)
        #print pubkey, public_key_to_bc_address(pubkey)
#            sha256 = message.tx.sha256
#            pubkey = binascii.hexlify(message.tx.vout[0].scriptPubKey)
#            txlock.acquire()
#            tx.append([str(sha256), str(time.time()), str(self.dstaddr), pubkey])
#            txlock.release()
        '''
        
class P2PFactory(ReconnectingClientFactory):
    def __init__(self, protocol):
        self.protocol = protocol
    
    def startFactory(self):
        ReconnectingClientFactory.startFactory(self)

    def buildProtocol(self, addr):
        self.resetDelay()
        return self.protocol()

def shutdown():
    print "Shutting down P2P connection"
    print "TODO: Save memory pool"
    
def run(host):
    log.info("Connecting to trusted Bitcoin node at %s" % host)
    reactor.connectTCP(host, 8333, P2PFactory(AlternateP2PProtocol))
    reactor.connectTCP(host, 8333, P2PFactory(MainP2PProtocol))
    reactor.addSystemEventTrigger('before', 'shutdown', shutdown)
