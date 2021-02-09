"""
This example is meant to show the basic bidirectional communications
between EagleDaddyHub and Cloud.

If installing a new hub, the cloud has no knowledge about the existence of the hub.
At first, the hub sends an announcement command to the cloud which contains
information about itself.

The cloud listens on a specific channel for announcements and processes them
accordingly, hub will send announcements either to 1) check in or 2) acknowledge 
its existence. 

If the cloud sees an annoucement from an non-existing hub, it will create a private listening channel using
the uid of the hub in the format 

/eagledaddy/<hub_id>

the cloud will communicate with the hub in the following channel

/eagledaddy/<hub_id>/cloud
"""

from edcomms import EDChannel, EDClient, EDCommand, EDPacket, MessageCallback
import uuid
import time


class ExampleCallBack(MessageCallback):
    def process(self):
        print(self.packet.describe())


class ExampleAnnounceProcessing(MessageCallback):
    def process(self):
        print(f"Caught an announcement: {self.packet.describe()}")
        sender_id = self.packet.sender_id
        self.client.add_subscription(EDChannel(f"{sender_id}/"),
                                     callback=ExampleCallBack)


if __name__ == '__main__':
    host = "127.0.0.1"

    cloud_id = uuid.uuid4()
    hub_id = uuid.uuid4()

    cloud = EDClient(cloud_id, host=host).init()
    hub = EDClient(hub_id, host=host).init()
    cloud.loop_start()
    hub.loop_start()

    cloud.add_subscription(EDChannel(""), callback=ExampleCallBack)
    cloud.add_subscription(EDChannel("announce/"),
                           callback=ExampleAnnounceProcessing)

    hub_listen = EDChannel("1234/cloud")
    hub.add_subscription(hub_listen, callback=ExampleCallBack)

    hub_announce = hub.create_packet(EDCommand.announce, None)
    hub.publish(EDChannel("announce/"), hub_announce)

    time.sleep(1)
    cloud_packet = cloud.create_packet(EDCommand.discovery, None)

    # here we explicitly provide hub_id to chat to device
    # in reality, this hub will be stored in a database
    # and the channel constructed by using the hubs data
    cloud.publish(EDChannel(f"{hub_id}/"), cloud_packet)
    time.sleep(1)

    hub.loop_stop()
    cloud.loop_stop()
