"""
A universal comms library that can be used by both EagleDaddyCloud
to communicate with Hubs and for Hubs to communicate with Eagle Daddy Cloud.
"""
import logging
import pickle
import sys
from typing import Any
import uuid
import paho.mqtt.client as mqtt
from enum import IntEnum

MQTTv31 = mqtt.MQTTv31
MQTTv311 = mqtt.MQTTv311

_ROOT_CHANNEL = "/eagledaddy"


class ChannelMisMatchException(Exception):
    pass


class MessageInfo(mqtt.MQTTMessageInfo):
    """
    Subclass of MQTT default MQTTMessageInfo.
    """
    def __init__(self, parentobj):
        super().__init__(parentobj.mid)

    def describe(self):
        """Describes this object"""
        return {
            'rc': mqtt.error_string(self.rc),
            'mid': f'MessageId: {self.mid}'
        }


class EDCommand(IntEnum):
    """
    Universal command structure that handles
    default definitions of different commands, as
    well as supports extensibility for future commands.
    """
    unknown = -2
    nack = -1
    ack = 0
    ping = 1
    pong = 2
    discovery = 3
    announce = 4


class EDPacket:
    """
    Universal packet structure that is understandable between
    all eagledaddy products
    """
    command = None
    sender_id = None
    payload = None

    def set_command(self, cmd: EDCommand):
        logging.debug(f"attaching command to packet: {cmd.name}")
        self.command = cmd
        return self

    def set_sender(self, sender_id: uuid.UUID):
        logging.debug(f"attaching sender to packet: {sender_id}")

        self.sender_id = sender_id
        return self

    def set_payload(self, payload: Any):
        logging.debug(f"attaching payload to packet: {payload}")

        self.payload = payload
        return self

    def describe(self):
        desc = f"""
Command: {self.command.name}
Sender: {self.sender_id}
Payload ({type(self.payload)}):

{self.payload}
"""
        return desc

    def __eq__(self, o: object) -> bool:
        return self.command == o.command and self.sender_id == o.sender_id and self.payload == o.payload


class EDChannel:
    def __init__(self, channel: str, root=None):

        self.root_sub = _ROOT_CHANNEL if not root else root

        self.channel_split = list(filter(None, channel.split('/')))
        self.channel = f"{self.root_sub}/{'/'.join(self.channel_split)}"

    def __contains__(self, obj):
        obj_root = obj.root.split('#')[0]
        self_root = self.root.split('#')[0]
        return self_root in obj_root

    def __str__(self):
        return f"<{self.channel}>"

    def __repr__(self):
        return self.__str__()

    @property
    def root(self):
        if not self.channel_split or len(self.channel_split) == 1:
            return f"{self.root_sub}/#"
        else:
            return f"{self.root_sub}/{'/'.join(self.channel_split[:-1])}/#"


class MessageCallback:
    """
    Abstract class that allows class-based processing
    of MQTT callbacks using paho-mqtt client.

    processing incoming mqtt message using `MessageCallback.process`
    Basic Usage:
    ```python
    client = MQTTClient()
    client.subscribe("#")
    client.message_callback_add("/specific/channel", MessageCallback.callback)
    ```
    """
    def __init__(self, client, channel, packet: EDPacket) -> None:
        self.client: mqtt.Client = client
        self.channel: str = channel
        self.packet: EDPacket = packet

    @classmethod
    def callback(cls, client, obj, msg: bytes):
        channel: str = msg.topic
        packet = pickle.loads(msg.payload)
        logging.debug(f"callback triggered for {packet.sender_id}")

        obj = cls(client, channel, packet)
        obj.process()

    def process(self):
        raise NotImplementedError()


class NoCallback(MessageCallback):
    def process(self):
        pass


class EDClient(mqtt.Client):
    _QOS = 2

    def __init__(self, device_id: uuid.UUID, host, port=1883):

        self.client_id = device_id
        self.subscriptions = list()
        self.host = host
        self.port = port
        self._root_subscription = None

        params = {
            'client_id': str(device_id),
            'protocol': mqtt.MQTTv311,
            'transport': 'tcp',
            'clean_session': False
        }

        super().__init__(**params)
        logging.debug(f"Initializing client with: {params}")

    def init(self):
        self.connect(host=self.host, port=self.port)
        logging.debug(f"Connecting to broker {self.host}:{self.port}")
        return self

    def run(self):
        raise NotImplementedError()

    def on_message(self, client, userdata, msg: bytes):
        """
        by default root subscription ignores messages
        """
        logging.debug(
            f"ignoring unhandeld subscription: {msg.topic}, size of data {_size_of(msg.payload)}KB"
        )

    def add_subscription(self, channel: EDChannel, callback: MessageCallback):
        """
        Adds subscriptions with specific callbacks.
        The very first time this method is called sets the root
        subscription, which dictates if future subscriptions are allowed.

        This is because the paho mqtt client has a built specific message callback methods
        via mqtt.Client.message_callback_*. However, for them to work correctly, the client
        needs to be subscribed to the root of the channel in order to handle specific channels.


        Example:
        root subscription -> /eagledaddy/#
        
        # call backs will now work on 
        callback1 -> /eagledaddy/callback1
        callback2 -> /eagledaddy/callback2

        """
        if not self._root_subscription:
            logging.info(
                f"Root subscription for {self.client_id} not found, creating one from supplied channel: {channel.root}"
            )
            self._root_subscription = channel.root
            self.subscribe(channel.root, qos=self._QOS)

        else:
            if channel not in self.subscriptions[0]:
                raise ChannelMisMatchException(
                    "attempting to add channel callback that is invalid in set root channel."
                )

        logging.info(
            f"Client {self.client_id} created callback for {channel.channel}")
        self.subscriptions.append(channel)

        if not callback:
            callback = NoCallback
            logging.info(
                'ignoring callback for {self.client_id}:{channel.channel}')

        self.message_callback_add(channel.channel, callback=callback.callback)

    def publish(self, channel: EDChannel, packet: EDPacket):
        encoded = pickle.dumps(packet)

        logging.debug(
            f"{self.client_id} publish payload on {channel.channel}: packet size {_size_of(packet)}KB"
        )
        info = super().publish(topic=channel.channel,
                               payload=encoded,
                               qos=self._QOS)
        return MessageInfo(info)

    def create_packet(self, cmd: EDCommand, payload: Any) -> EDPacket:
        packet = EDPacket().set_command(cmd) \
            .set_payload(payload) \
            .set_sender(self.client_id)
        return packet


def _size_of(packet: Any):
    if isinstance(packet, EDPacket):
        return round(sys.getsizeof(pickle.dumps(packet)) / 1000, 2)

    return round(sys.getsizeof(packet) / 1000, 2)
