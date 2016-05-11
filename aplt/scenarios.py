"""Several basic push scenarios"""
from twisted.python import log

from aplt.commands import (
    connect,
    hello,
    register,
    send_notification,
    expect_notification,
    expect_notifications,
    unregister,
    disconnect,
    ack,
    random_channel_id,
    random_data,
    timer_start,
    timer_end,
    counter,
    wait,
    spawn,
)
from aplt.decorators import restart
from aplt.utils import bad_push_endpoint


def basic(*args):
    """Connects, sends a notification, than disconnects"""
    yield connect()
    yield hello(None)
    reg = yield register(random_channel_id())
    yield timer_start("update.latency")
    response, content = yield send_notification(reg["pushEndpoint"], None, 60)
    yield counter("notification.sent", 1)
    notif = yield expect_notification(reg["channelID"], 5)
    yield counter("notification.received", 1)
    yield timer_end("update.latency")
    log.msg("Got notif: ", notif)
    yield ack(channel_id=notif["channelID"], version=notif["version"])
    yield counter("notification.ack", 1)
    yield unregister(reg["channelID"])
    yield disconnect()


def connect_and_idle_forever():
    """Connects without ever disconnecting"""
    yield connect()
    yield hello(None)

    while True:
        yield wait(100)


def reconnect_forever(reconnect_delay=30, run_once=0):
    """Connects, then repeats every delay interval:
    1. send notification
    2. receive notification
    3. disconnect
    4. reconnect

    Repeats forever.
    """
    yield connect()
    response = yield hello(None)

    reg = yield register(random_channel_id())
    assert "uaid" in response
    uaid = response["uaid"]

    while True:
        length, data = random_data(min_length=2048, max_length=4096)
        yield timer_start("update.latency")
        response, content = yield send_notification(reg["pushEndpoint"], data,
                                                    60)
        yield counter("notification.throughput.bytes", length)
        yield counter("notification.sent", 1)
        notif = yield expect_notification(reg["channelID"], 5)
        yield counter("notification.received", 1)
        yield ack(channel_id=notif["channelID"], version=notif["version"])
        yield counter("notification.ack", 1)
        yield timer_end("update.latency")
        yield wait(reconnect_delay)
        yield disconnect()
        yield connect()
        response = yield hello(uaid)
        assert response["uaid"] == uaid

        if run_once:
            yield unregister(reg["channelID"])
            yield disconnect()
            break


def register_forever(reg_delay=30, run_once=0):
    """Connects, then repeats every delay interval:
    1. register

    Repeats forever.
    """
    yield connect()
    yield hello(None)
    while True:
        reg = yield register(random_channel_id())
        yield wait(reg_delay)

        if run_once:
            yield unregister(reg["channelID"])
            yield disconnect()
            break


def notification_forever(notif_delay=30, run_once=0):
    """Connects, then repeats every delay interval:
    1. send notification
    2. receive notification

    Repeats forever.
    """
    yield connect()
    yield hello(None)
    reg = yield register(random_channel_id())

    while True:
        length, data = random_data(min_length=2048, max_length=4096)
        yield timer_start("update.latency")
        response, content = yield send_notification(reg["pushEndpoint"], data,
                                                    60)
        yield counter("notification.throughput.bytes", length)
        yield counter("notification.sent", 1)
        notif = yield expect_notification(reg["channelID"], 5)
        yield counter("notification.sent", 1)
        yield timer_end("update.latency")
        yield ack(channel_id=notif["channelID"], version=notif["version"])
        yield counter("notification.ack", 1)
        yield wait(notif_delay)

        if run_once:
            yield unregister(reg["channelID"])
            yield disconnect()
            break


def notification_forever_unsubscribed(notif_delay=30, run_once=0):
    """Connects, registers, unregisters, then repeat following steps
    every delay interval (ignoring 4XXs):
    1. send notification
    2. receive notification

    Repeats forever.
    """
    yield connect()
    yield hello(None)
    reg = yield register(random_channel_id())
    unregister(reg["channelID"])

    while True:
        length, data = random_data(min_length=2048, max_length=4096)
        yield timer_start("update.latency")
        response, content = yield send_notification(reg["pushEndpoint"], data,
                                                    60)
        yield counter("notification.throughput.bytes", length)
        yield counter("notification.sent", 1)
        notif = yield expect_notification(reg["channelID"], 5)
        yield counter("notification.sent", 1)
        yield timer_end("update.latency")
        yield ack(channel_id=notif["channelID"], version=notif["version"])
        yield counter("notification.ack", 1)
        yield wait(notif_delay)

        if run_once:
            yield unregister(reg["channelID"])
            yield disconnect()
            break


def notification_forever_bad_tokens(notif_delay=30, run_once=0,
                                    token_length=140):
    """Connects, then repeats every delay interval:
    1. send notification with invalid token

    Repeats forever.
    """
    yield connect()
    yield hello(None)

    # register only to retrieve valid endpoint path
    # (we'll replace valid token with invalid one)
    reg = yield register(random_channel_id())

    while True:
        push_endpoint = bad_push_endpoint(reg["pushEndpoint"],
                                          token_length)
        length, data = random_data(min_length=2048, max_length=4096)
        response, content = yield send_notification(push_endpoint, data,
                                                    60)
        yield counter("notification.throughput.bytes", length)
        yield counter("notification.sent", 1)

        yield wait(notif_delay)
        if run_once:
            yield disconnect()
            break


def notification_forever_bad_endpoints(notif_delay=30, run_once=0):
    """Connects, repeats every delay interval:
    1. send notification with invalid endpoint.

    Repeats forever.
    """
    yield connect()
    yield hello(None)

    while True:
        push_endpoint = bad_push_endpoint()
        length, data = random_data(min_length=2048, max_length=4096)
        response, content = yield send_notification(push_endpoint, data,
                                                    60)
        yield counter("notification.throughput.bytes", length)
        yield counter("notification.sent", 1)

        yield wait(notif_delay)
        if run_once:
            yield disconnect()
            break


##############################################################################
# TEST SCENARIOS
##############################################################################
_RESTARTS = 0


@restart(2)
def _explode():
    global _RESTARTS
    yield connect()
    _RESTARTS += 1
    yield connect()


def _test_spawn():
    yield spawn("aplt.scenarios:basic, 1, 1, 0")


def _test_multiple_spawn():
    yield spawn("aplt.scenarios:basic, 1, 1, 0")
    yield spawn("aplt.scenarios:basic, 1, 1, 0")
    yield spawn("aplt.scenarios:basic, 1, 1, 0")
    yield spawn("aplt.scenarios:basic, 1, 1, 0")


def _expect_notifications():
    from random import shuffle
    yield connect()
    yield hello(None)
    chan_regs = []
    for chan in [random_channel_id() for _ in range(10)]:
        reg = yield register(chan)
        yield send_notification(reg["pushEndpoint"], None, 60)
        # Server may reformat the channel id, use that one
        chan_regs.append(reg["channelID"])
    shuffle(chan_regs)
    for _ in range(10):
        notif = yield expect_notifications(chan_regs, 5)
        log.msg("Got notif: ", notif)
        yield ack(channel_id=notif["channelID"], version=notif["version"])
    for chid in chan_regs:
        yield unregister(chid)
    yield disconnect()
