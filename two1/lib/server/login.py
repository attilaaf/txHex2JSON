import base64
import click
import re
from two1.commands.config import TWO1_HOST
from two1.commands.exceptions import ServerConnectionError
from two1.commands.exceptions import ServerTimeout
from two1.lib.server.machine_auth_wallet import MachineAuthWallet
from two1.lib.server.rest_client import TwentyOneRestClient
from two1.lib.util.uxstring import UxString


class EmailAddress(click.ParamType):
    name = "Email address"

    def __init__(self):
        click.ParamType.__init__(self)

    def convert(self, value, param, ctx):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", value):
            self.fail(UxString.invalid_email)
        return value


def check_setup_twentyone_account(config):
    """ Checks for a working wallet and a 21 a/c.
    Sets up the a/c and configures a wallet if needed.

    Args:
        config (Config): Config object from the cli
    """
    # check if a/c has been setup with a proper username
    if not config.mining_auth_pubkey:
        click.echo(UxString.missing_account)
        username = create_twentyone_account(config)
        if not username:
            click.echo(UxString.account_failed)
            return False


def create_twentyone_account(config):
    """ Attempts to create a 21 a/c using the username that exists
    in the config object.

    Args:
        config (Config): Config object from the cli context.

    Returns:
        str: Returns the username that was created, None otherwise
    """
    try:
        create_username(config)
        return config.username
    except ServerConnectionError:
        click.echo(UxString.Error.connection % TWO1_HOST)
    except ServerTimeout:
        click.echo(UxString.Error.timeout % TWO1_HOST)

    return None


def create_username(config, username=None):
    """ Creates a private auth key and associates it with a 21 account.
    If the username already exists, it prompts the user for the new username.
    The private key is saved in system default keyring. The config is updated
    and saved with the username and the base64 encoded public key.

    Args:
        config (Config):  Config object from the cli context.
        username (str): Attempt to create the user with this username.

    Returns:
        str: The username that the a/c was created with.
    """
    # twentyone a/c setup
    # simple key generation
    # TODO: this can be replaced with a process where the user
    # can hit a few random keystrokes to generate a private
    # key
    # check if a key already exists and use it
    machine_auth = config.machine_auth
    if not machine_auth:
        raise ValueError("Error: Auth is not initialized.")
    # get public key and convert to base64 for storage
    machine_auth_pubkey_b64 = base64.b64encode(
        machine_auth.public_key.compressed_bytes
    ).decode()
    # use the same key for the payout address as well.
    # this will come from the wallet
    bitcoin_payout_address = config.wallet.current_address
    rest_client = TwentyOneRestClient(TWO1_HOST, machine_auth)

    while True:
        if username == "" or username is None:
            username = click.prompt(UxString.enter_username, type=click.STRING)
            click.echo(UxString.creating_account % username)
        r = rest_client.account_post(username, bitcoin_payout_address)
        if r.status_code == 200:
            break
        elif r.status_code == 201:
            click.echo(UxString.payout_address % bitcoin_payout_address)
            config.update_key("username", username)
            config.update_key("mining_auth_pubkey", machine_auth_pubkey_b64)
            config.save()
            break
        elif r.status_code == 400:
            click.echo(UxString.username_exists % username)
            username = None
        else:
            username = None
    return username
