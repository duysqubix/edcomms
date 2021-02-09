import unittest
import uuid
import time
from edcomms import EDChannel, EDClient, EDCommand, EDPacket, MessageCallback, NoCallback

BROKER_HOST = "broker.hivemq.com"
BROKER_PORT = 1883


class TestEDChannel(unittest.TestCase):
    def setUp(self) -> None:
        root = '/dummy'
        self.ch0 = EDChannel("", root=root)
        self.ch1 = EDChannel("test/", root=root)
        self.ch2 = EDChannel("test/channel", root=root)
        self.ch3 = EDChannel("test/channel/01", root=root)

    def test_root_parsing(self):
        ch0_valid_root = "/dummy/#"
        ch1_valid_root = "/dummy/#"
        ch2_valid_root = "/dummy/test/#"
        ch3_valid_root = "/dummy/test/channel/#"
        self.assertEqual(ch0_valid_root, self.ch0.root)
        self.assertEqual(ch1_valid_root, self.ch1.root)
        self.assertEqual(ch2_valid_root, self.ch2.root)
        self.assertEqual(ch3_valid_root, self.ch3.root)

    def test_contains(self):
        self.assertTrue(self.ch0 in self.ch0)
        self.assertTrue(self.ch0 in self.ch1)

        self.assertFalse(self.ch1 in self.ch2)
        self.assertTrue(self.ch2 in self.ch1)

        self.assertFalse(self.ch2 in self.ch3)
        self.assertTrue(self.ch3 in self.ch2)

        self.assertFalse(self.ch1 in self.ch3)
        self.assertTrue(self.ch3 in self.ch1)


class TestEDClient(unittest.TestCase):
    def setUp(self) -> None:
        self.pub_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        self.sub_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        self.master = EDClient(self.pub_id, host=BROKER_HOST, port=BROKER_PORT)
        self.slave = EDClient(self.sub_id, host=BROKER_HOST, port=BROKER_PORT)

        # connect to host
        self.master.init()
        self.slave.init()

    def test_create_packet(self):
        command = EDCommand.ack
        data = {"hello": "world"}
        gen_packet = self.master.create_packet(command, data)
        valid_packet = EDPacket().set_command(command).set_payload(
            data).set_sender(self.pub_id)
        self.assertTrue(gen_packet == valid_packet)

    def test_subscription_and_callback(self):
        class TestCallBack(MessageCallback):
            def process(s):
                self.assertEqual(s.packet.command, EDCommand.ack)

        channel = EDChannel('test/01', root='/dummy')
        self.slave.add_subscription(channel, callback=TestCallBack)
        self.assertIn(channel, self.slave.subscriptions)
        self.slave.loop_start()
        p = self.slave.create_packet(EDCommand.ack, {'hello': 'world'})
        self.slave.publish(channel, p)
        time.sleep(1)
        self.slave.loop_stop()

    def test_bidirectional_comms(self):
        """
        mini test for bi-directional communication between
        a master and a slave.

        Each callback will be called only once and that is what this unittest tests for.

        The general gist is the following:

        master and slave clients

        slave announces to master.
        Master detects announcement and responds with acknowledgment
        """
        self.master.test = self
        self.slave.test = self

        root_channel = "/dummy"

        self.master_rcvd_packet = 0
        self.announce_rcvd_packet = 0

        class SlaveToMasterCallback(MessageCallback):
            def process(s):
                # print(s.packet.describe())
                s.client.test.master_rcvd_packet += 1

        class AnnounceCallBack(MessageCallback):
            def process(s):
                # print(s.packet.describe())

                sender_id = s.packet.sender_id

                direct_channel = EDChannel(f"{sender_id}/cloud",
                                           root=root_channel)
                s.client.add_subscription(direct_channel,
                                          callback=SlaveToMasterCallback)
                self.assertIn(direct_channel, s.client.subscriptions)
                s.client.test.announce_rcvd_packet += 1

        self.master.loop_start()
        self.slave.loop_start()

        master_root_channel = EDChannel("", root=root_channel)
        announce_channel = EDChannel("announce/", root=root_channel)
        slave_listen_channel = EDChannel(f"{self.slave.client_id}/cloud")

        self.master.add_subscription(master_root_channel, callback=None)

        self.master.add_subscription(announce_channel,
                                     callback=AnnounceCallBack)

        self.slave.add_subscription(slave_listen_channel,
                                    callback=SlaveToMasterCallback)

        announce_packet = self.slave.create_packet(EDCommand.announce,
                                                   payload=None)

        # send back acknowledgement

        self.slave.publish(announce_channel, announce_packet)
        time.sleep(1)
        direct_channel = self.master.subscriptions[-1]
        ack_packet = self.master.create_packet(EDCommand.ack, None)
        self.master.publish(direct_channel, ack_packet)
        time.sleep(1)
        self.master.loop_stop()
        self.slave.loop_stop()
        self.assertEqual(self.master_rcvd_packet, 1)
        self.assertEqual(self.announce_rcvd_packet, 1)