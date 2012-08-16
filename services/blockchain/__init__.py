from twisted.internet import defer

from stratum.services import GenericService
import stratum.helpers as helpers
import stratum.settings as settings

import p2pnode
p2pnode.run(settings.BITCOIN_TRUSTED_HOST)

import stratum.logger
log = stratum.logger.get_logger('service.blockchain')

class BlockchainBlockService(GenericService):
    service_type = 'blockchain.block'
    service_vendor = 'Electrum'
    is_default = True
    
    def subscribe(self):
        return True
    
    def unsubscribe(self):
        return True

    def get_blocknum(self):
        # FIXME: Own implementation
        return helpers.ask_old_server('b')
    
class BlockchainAddressService(GenericService):
    service_type = 'blockchain.address'
    service_vendor = 'Electrum'
    is_default = True
    
    def subscribe(self, address):
        return True
    
    def unsubscribe(self, address):
        return True

    def get_history(self, address):
        # FIXME: Own implementation
        return helpers.ask_old_server('h', address)
    
    def get_balance(self, address):
        # FIXME: Own implementation
        return helpers.ask_old_server('b', address)
    
class BlockchainTransactionService(GenericService):
    service_type = 'blockchain.transaction'
    service_vendor = 'Electrum'
    is_default = True
    
    def subscribe(self):
        return True
    
    def unsubscribe(self):
        return True

    def guess_fee(self):
        # FIXME: Blockchain analysis
        return 0.0005
    
    @defer.inlineCallbacks
    def broadcast(self, transaction):
        try:
            txhash = (yield p2pnode.get_connection().broadcast_tx(transaction))
        except:
            raise Exception("Transaction has been rejected by Bitcoin network")
        defer.returnValue(txhash)

    def get(self, hash):
        raise NotImplemented
