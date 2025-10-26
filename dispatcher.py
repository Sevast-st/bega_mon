import abc
import logging
from typing import Dict, Optional

# Configure a simple logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AlertChannel(abc.ABC):
    """Abstract base class for an alert channel."""

    @abc.abstractmethod
    def send(self, message: str) -> None:
        """
        Sends an alert message through the channel.

        Args:
            message: The alert message string to send.
        """
        pass

class ConsoleChannel(AlertChannel):
    """An alert channel that prints messages to the console."""

    def send(self, message: str) -> None:
        """
        Prints the alert message to the console using the logger.

        Args:
            message: The alert message string to print.
        """
        logger.info(f"[CONSOLE ALERT] {message}")

class AlertDispatcher:
    """Dispatches alerts to registered channels."""

    def __init__(self) -> None:
        self._channels: Dict[str, AlertChannel] = {}
        logger.info("AlertDispatcher initialized.")

    def register_channel(self, name: str, channel: AlertChannel) -> None:
        """
        Registers a new alert channel.

        Args:
            name: A unique name for the channel (e.g., 'console', 'slack').
            channel: An instance of a class that inherits from AlertChannel.

        Raises:
            ValueError: If a channel with the same name is already registered.
        """
        if name in self._channels:
            raise ValueError(f"Channel '{name}' is already registered.")
        self._channels[name] = channel
        logger.info(f"Alert channel '{name}' registered.")

    def dispatch(self, message: str, channel_name: Optional[str] = None) -> None:
        """
        Dispatches an alert message to one or all channels.

        If a channel_name is specified, the message is sent only to that
        channel. Otherwise, it is broadcast to all registered channels.

        Args:
            message: The alert message to dispatch.
            channel_name: The name of the specific channel to send the alert to.
        """
        if channel_name:
            if channel_name in self._channels:
                logger.debug(f"Dispatching alert to specific channel: {channel_name}")
                self._channels[channel_name].send(message)
            else:
                logger.warning(f"Attempted to dispatch to unregistered channel: {channel_name}")
        else:
            if not self._channels:
                logger.warning("No alert channels registered. Alert not sent.")
                return
            
            logger.debug("Broadcasting alert to all registered channels.")
            for name, channel in self._channels.items():
                try:
                    channel.send(message)
                except Exception as e:
                    logger.error(f"Failed to send alert via channel '{name}': {e}", exc_info=True)
