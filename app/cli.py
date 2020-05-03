# click app exercising the various components
import os
import click
from app import stockist


class Config(object):

    def __init__(self):
        self.verbose = False
        self.debug = False
        self.silent = False
        self.default_database = ".stockist.db"
        self.default_verbose = False
        self.default_debug = False
        self.default_silent = False
        self.default_lock = False
        self._default_verbose_spec = bool
        self._default_debug_spec = bool
        self._default_silent_spec = bool
        self._default_database_spec = str
        self.config = "~/.stockistconfig"
    
    def __setattr__(self, name, value):
        spec = getattr(self, "_{}_spec".format(name), None)
        super(Config, self).__setattr__(name, value if spec is None else spec(value))

    @property
    def silent(self):
        return self._silent

    @silent.setter
    def silent(self, value):
        if value:
            click.echo = lambda m: None
            click.secho = lambda m, **w: None
        self._silent = value

    def initialise_defaults(self):
        try:
            with open(os.path.expanduser(self.config), 'r') as fh:
                for line in fh.readlines():
                    if line.startswith('default'):
                        name, value = line.split('=')
                        setattr(self, name, value.strip())
                        if self.debug:
                            click.secho('Set {0} to {1}.'.format(name, value), fg="cyan")
        except (IOError, OSError):
            if self.debug:
                click.secho('Config file does not yet exist.', fg="red")

    def reset_defaults(self):
        try:    
            with open(os.path.expanduser(self.config), 'w') as fh:
                pass
        except (IOError, OSError):
            if self.debug:
                click.secho('Error writing to config file.', fg="red")

    def set_default(self, name, value):
        if name.startswith('default') and name in dir(self):
            setattr(self, name, value)
            if self.debug:
                click.secho('Set {0} to {1}.'.format(name, value), fg="cyan")
        else:
            click.secho('Invalid name.', fg="red")
            return
        try:
            with open(os.path.expanduser(self.config), 'w') as fh:
                for attribute in dir(self):
                    if attribute.startswith('default'):
                        value_to_write = getattr(self, attribute)
                        if value_to_write:
                            fh.write("%s=%s\n" % (attribute, value_to_write))
                            if self.debug:
                                click.secho('Wrote %s to file.' % (attribute,), fg="cyan")
        except (IOError, OSError):
            if self.debug:
                click.secho('Error writing to config file.', fg="red")


pass_config = click.make_pass_decorator(Config, ensure=True)


@click.group()
@click.option('--verbose', is_flag=True)
@click.option('--debug', is_flag=True)
@click.option('--silent', is_flag=True)
@click.option('--database', default=None)
@click.option('--lock', is_flag=True)
@pass_config
def cli(config, verbose, debug, silent, database, lock):

    config.initialise_defaults()
    if verbose or config.default_verbose:
        click.echo('Defaults initialised.')

    config.verbose = verbose | bool(config.default_verbose)
    config.debug = debug | bool(config.default_debug) 
    config.silent = silent | bool(config.default_silent)
    config.stock = stockist.SQLiteStockist(database or config.default_database)
    try:
        config.stock.create_database()
        config.stock.update_stock_from_db()
        config.stock.stock_locked = lock | bool(config.default_lock)
    except stockist.StockError:
        click.secho('No database!', fg="red")

    if debug or config.default_debug:
        click.secho(
            'Database set to {0}.'
            .format(database or config.default_database),
            fg="cyan"
        )
        click.secho(
            'Verbose set to {0}.'
            .format(config.verbose), 
            fg="cyan"
        )
        click.secho(
            'Debug set to {0}.'
            .format(config.debug), 
            fg="cyan"
        )


@cli.command()
@click.argument('name')
@click.argument('value')
@pass_config
def set(config, name, value):
    value = {
        'true': True,
        'false': False
    }.get(value.lower(), value)
    config.set_default('default_{0}'.format(name), value)


@cli.command()
@pass_config
def reset(config):
    config.reset_defaults()


@cli.command()
@pass_config
def clear(config):
    if click.confirm('Clear all stock?'):
        config.stock.reset_database()
        if config.verbose:
            click.echo('Cleared.')


@cli.command()
@pass_config
def defaults(config):
    for default in dir(config):
        if default.startswith('default'):
            click.echo('{0}: {1}'.format(default, getattr(config, default)))


@cli.command()
@pass_config
def listall(config):
    for name, mapping in config.stock.name_id_map.items():
        click.echo()
        click.echo('=' * 20)
        click.echo(name)
        click.echo('=' * 20)
        for i, unique in sorted(mapping):
            click.echo("> " + unique + ": " + str(config.stock[i]['count']))
        click.echo('=' * 20)
        click.echo()


@cli.command()
@click.argument('name', default='')
@pass_config
def listname(config, name):
    if name in config.stock:
        click.echo()
        click.echo('=' * 20)
        click.echo(name)
        click.echo('=' * 20)
        for stock in config.stock.stock_for_item(name):
            click.echo("> " + stock['unique_name'] + ": " + str(stock['count']))
        click.echo('=' * 20)
        click.echo()
    else:
        click.secho('Not found.', fg="red")


@cli.command()
@click.argument('name-or-id')
@pass_config
def count(config, name_or_id):
    try:
        try:
            click.echo(config.stock[int(name_or_id)]['count'])
        except ValueError:
            for stock in config.stock[name_or_id]:
                click.echo("> " + stock['unique_name'] + ": " + str(stock['count']))
    except KeyError:
        click.secho('Not found.', fg="red")


@cli.command()
@click.argument('name-or-id')
@click.argument('amount', default=1)
@click.option('--create', is_flag=True)
@pass_config
def stock(config, name_or_id, amount, create):
    try:
        amount = int(amount)
    except ValueError:
        click.secho('Invalid amount.', fg="red")
        return
    try:
        try:
            i = config.stock.stock_item(item_id=int(name_or_id), amount=amount, create=create)
        except ValueError:
            i = config.stock.stock_item(item=name_or_id, amount=amount, create=create)
    except stockist.StockLockedError:
        click.secho('Locked.', fg="red")
    if config.verbose:
        click.echo(config.stock[i]['unique_name'] + ": " + str(config.stock[i]['count']))


@cli.command()
@click.argument('name-or-id')
@click.argument('amount', default=-1)
@click.option('--delete-if-zero', is_flag=True)
@pass_config
def remove(config, name_or_id, amount, delete_if_zero=False):
    try:
        amount = abs(int(amount)) * -1
    except ValueError:
        click.secho('Invalid amount.', fg="red")
        return
    try:
        key = int(name_or_id)
    except ValueError:
        key = config.stock.last_stock_id_for_item(name_or_id)
    if key is not None:
        try:
            config.stock.increase_stock(key, amount)
            if config.stock[key]['count'] < 1 and delete_if_zero:
                del config.stock[key]
                if config.verbose:
                    click.echo('Deleted.')
            elif config.verbose:
                click.echo(config.stock[key]['unique_name'] + ": " + str(config.stock[key]['count']))
        except KeyError:
            click.secho('Not found.', fg="red")
        except stockist.StockLockedError:
            click.secho('Locked.', fg="red")
    elif config.verbose:
        click.echo('Not present.')
    

@cli.command()
@click.argument('name-or-id')
@click.option('--delete-all', is_flag=True)
@pass_config
def delete(config, name_or_id, delete_all=False):
    try:
        key = int(name_or_id)
    except ValueError:
        key = name_or_id if delete_all else config.stock.last_stock_id_for_item(name_or_id)
    if key is not None:
        try:
            del config.stock[key]
        except stockist.StockLockedError:
            click.secho('Locked.', fg="red")
