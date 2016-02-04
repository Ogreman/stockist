# stock management (items, count, database)
import collections
import sqlite3
import psycopg2


class StockError(Exception):
    pass


class StockLockedError(StockError):
    pass


class StockConnectionError(StockError):
    pass


def locked_method(method):
    def wrapped(instance, *args, **kwargs):
        if instance.is_locked:
            raise StockLockedError
        else:
            return method(instance, *args, **kwargs)
    return wrapped


class Stockist(object):

    @property
    def stock_locked(self):
        if not hasattr(self, '_lock_stock'):
            self._lock_stock = False
        return self._lock_stock

    @stock_locked.setter
    def stock_locked(self, value):
        if not isinstance(value, bool):
            raise ValueError
        self._lock_stock = value
    
    def lock_stock_list(self):
        self.stock_locked = True
    
    def unlock_stock_list(self):
        self.stock_locked = False
    
    @property
    def is_locked(self):
        return self.stock_locked

    @property 
    def stock(self):
        if not hasattr(self, '_stock'):
            self._stock = collections.OrderedDict()
        return self._stock

    @property
    def name_id_map(self):
        if not hasattr(self, '_name_id_map'):
            self._name_id_map = collections.OrderedDict()
        return self._name_id_map
    
    def stock_ids_for_item(self, item):
        return [stock_id for stock_id, _ in self.name_id_map.get(str(item), set())]

    def stock_for_item(self, item):
        return [
            self.stock[stock_id]
            for stock_id in self.stock_ids_for_item(item)
        ]

    def __getitem__(self, item_or_stock_id):
        if isinstance(item_or_stock_id, int):
            return self.stock[item_or_stock_id]
        return self.stock_for_item(item_or_stock_id)

    @locked_method
    def __setitem__(self, item_or_stock_id, item):
        if isinstance(item_or_stock_id, int):
            self.new_stock_item(item, new_id=item_or_stock_id)
        else:
            self.new_stock_item(item)

    @locked_method
    def __delitem__(self, item_or_stock_id):
        if isinstance(item_or_stock_id, int):
            self.delete_stock_entry(item_or_stock_id)
        else:
            for stock_id in self.stock_ids_for_item(item_or_stock_id):
                self.delete_stock_entry(stock_id)

    def __contains__(self, item_or_stock_id):
        if isinstance(item_or_stock_id, int):
            return item_or_stock_id in self.stock
        else:
            return str(item_or_stock_id) in self.name_id_map

    @property
    def stock_ids(self):
        return self.stock.keys()

    @property 
    def last_stock_id(self):
        try:
            return self.stock.keys()[-1]
        except IndexError:
            return None
    
    @property
    def last_stock_entry(self):
        try:
            return self.stock.values()[-1]
        except IndexError:
            return None

    @property
    def stock_count(self):
        return [
            (_id, details.get('count', 0))
            for _id, details in self.stock.items()
        ]

    @staticmethod
    def create_item_data(new_id, item, count=0):
        return {
            'stock_id': new_id,
            'unique_name': '%s_#%d' % (item, new_id),
            'count': count,
        }

    @property 
    def next_free_stock_id(self):
        if not hasattr(self, '_next_free_stock_id'):
            self._next_free_stock_id = 0
        while self._next_free_stock_id in self.stock:
            self._next_free_stock_id += 1
        return self._next_free_stock_id

    @locked_method
    def delete_stock_entry(self, old_id):
        data = self.stock[old_id]
        unique_name = data['unique_name']
        item_name, _ = unique_name.split('_#')
        self.name_id_map[item_name].discard((old_id, unique_name))
        del self.stock[old_id]

    @locked_method
    def new_stock_item(self, item, new_id=None, force=False):
        if item is None:
            raise StockError('Unable to process NoneType!')
        if new_id is None:
            new_id = self.next_free_stock_id
        if new_id in self.stock:
            if force:
                self.delete_stock_entry(new_id)
            else:
                raise StockError('Stock ID already in use!')
        item_data = self.create_item_data(new_id, item)
        existing_items = self.name_id_map.setdefault(str(item), set())
        existing_items.add((new_id, item_data['unique_name']))
        self.stock[new_id] = item_data
        return new_id

    def list_stocked_item_ids(self):
        return [_id for _id, count in self.stock_count if count > 0]

    def item_stocked(self, item):
        return str(item) in self.name_id_map

    def last_stock_id_for_item(self, item):
        try:
            return sorted(self.stock_ids_for_item(item))[-1]
        except IndexError:
            return None

    def last_stock_entry_for_item(self, item):
        return self.stock.get(self.last_stock_id_for_item(item), None)

    def stock_item(self, item=None, item_id=None, amount=1, create=False):
        if item is not None:
            if create or not self.item_stocked(item):
                item_id = self.new_stock_item(item, item_id)
            elif item_id is None:
                item_id = self.last_stock_id_for_item(item)
        self.increase_stock(item_id, amount)
        return item_id

    def increase_stock(self, stock_id, amount=1):
        self.stock[stock_id]['count'] += amount


class DatabaseStockist(Stockist):

    STOCK_TABLE = "stock"
    CREATE_SQL_STRING = "CREATE TABLE {table}(pk INT, name TEXT, count INT)"
    DROP_SQL_STRING = "DROP TABLE IF EXISTS {table}"
    SELECT_SQL_STRING = "SELECT {what} FROM {table};"
    INSERT_SQL_STRING = None
    DELETE_SQL_STRING = None

    StockEntry = collections.namedtuple('StockEntry', ['pk', 'name', 'count'])

    def __init__(self):
        self._connection = None

    @property
    def connection(self):
        if self._connection is None:
            raise StockConnectionError('No database connection!')
        return self._connection

    @connection.setter
    def connection(self, value):
        raise NotImplemented

    @staticmethod
    def select(cur, table_name, what="*"):
        cur.execute(DatabaseStockist.SELECT_SQL_STRING.format(what=what, table=table_name))
        return cur.fetchall()

    @locked_method
    def update_stock_from_db(self, force=False):
        if force or self.is_missing_stock_from_database:
            stock_data = self.database_stock
            for data in stock_data.values():
                item_name, _ = data['unique_name'].split('_#')
                existing_items = self.name_id_map.setdefault(item_name, set())
                existing_items.add((data['stock_id'], data['unique_name']))
            self.stock.update(stock_data)

    @property
    def is_database_up_to_date(self):
        stock_data = self.database_stock
        if self.stock and not stock_data:
            return False
        return set(stock_data).issuperset(set(self.stock))

    @property
    def is_missing_stock_from_database(self):
        stock_data = self.database_stock
        if stock_data and not self.stock:
            return True
        return bool(set(stock_data) - set(self.stock))

    def dump_stock_to_database(self):
        with self.connection as connection:
            cur = connection.cursor()
            cur.execute(self.DROP_SQL_STRING.format(table=self.STOCK_TABLE))
            cur.execute(self.CREATE_SQL_STRING.format(table=self.STOCK_TABLE))
            cur.executemany(
                self.INSERT_SQL_STRING.format(table=self.STOCK_TABLE),
                self.create_stock_entries()
            )
            connection.commit()

    def reset_database(self):
        with self.connection as connection:
            cur = connection.cursor()
            cur.execute(self.DROP_SQL_STRING.format(table=self.STOCK_TABLE))
            cur.execute(self.CREATE_SQL_STRING.format(table=self.STOCK_TABLE))
            connection.commit()

    def create_database(self):
        with self.connection as connection:
            cur = connection.cursor()
            cur.execute(self.CREATE_SQL_STRING.format(table=self.STOCK_TABLE))
            connection.commit()

    def update_database(self, force=False):
        if force:
            entries = self.create_stock_entries()
        else:
            stock_data = self.database_stock
            entries = [
                self.create_stock_entry(key)
                for key in self.stock.keys()
                if key not in stock_data
            ]
        with self.connection as connection:
            cur = connection.cursor()
            cur.executemany(
                self.INSERT_SQL_STRING.format(table=self.STOCK_TABLE),
                entries
            )
            connection.commit()

    def create_stock_entry(self, stock_id):
        data = self.stock[stock_id]
        return self.StockEntry(
            data['stock_id'],
            data['unique_name'],
            data['count'],
        )

    def create_stock_entries(self):
        return [
            self.StockEntry(
                data['stock_id'],
                data['unique_name'],
                data['count'],
            ) for data in self.stock.values()
        ]

    def new_stock_item(self, item, new_id=None, force=False, update_db=True):
        new_id = super(DatabaseStockist, self).new_stock_item(item, new_id, force)
        if self.INSERT_SQL_STRING is None and update_db:
            raise NotImplementedError
        elif update_db:
            with self.connection as connection:
                cur = connection.cursor()
                cur.execute(
                    self.INSERT_SQL_STRING.format(table=self.STOCK_TABLE),
                    self.create_stock_entry(new_id)
                )
                connection.commit()
        return new_id

    def delete_stock_entry(self, old_id, update_db=True):
        super(DatabaseStockist, self).delete_stock_entry(old_id)
        if self.DELETE_SQL_STRING is None and update_db:
            raise NotImplementedError
        elif update_db:
            with self.connection as connection:
                cur = connection.cursor()
                cur.execute(
                    self.DELETE_SQL_STRING.format(table=self.STOCK_TABLE), 
                    (old_id,)
                )
                connection.commit()

    def increase_stock(self, stock_id, amount=1, update_db=True):
        super(DatabaseStockist, self).increase_stock(stock_id, amount)
        if update_db:
            with self.connection as connection:
                cur = connection.cursor()
                cur.execute(
                    self.UPDATE_SQL_STRING.format(table=self.STOCK_TABLE),
                    (self.stock[stock_id]['count'], stock_id)
                )
                connection.commit()

    @property
    def database_stock(self):
        with self.connection:
            cur = self.connection.cursor()
            return {
                stock_id: {
                    'stock_id': stock_id,
                    'unique_name': name,
                    'count': count,
                }
                for stock_id, name, count in self.select(cur, self.STOCK_TABLE)
            }


class SQLiteStockist(DatabaseStockist):

    INSERT_SQL_STRING = "INSERT INTO {table} VALUES(?, ?, ?)"
    UPDATE_SQL_STRING = "UPDATE {table} SET count=? where pk=?"
    DELETE_SQL_STRING = "DELETE FROM {table} WHERE pk=?"

    def __init__(self, database=None):
        super(SQLiteStockist, self).__init__()
        self.connection = database
        self.memcon = sqlite3.connect(':memory:')
    
    @property
    def connection(self):
        connection = super(SQLiteStockist, self).connection
        if connection is not None:
            if connection.row_factory is None:
                connection.row_factory = sqlite3.Row
        return connection

    @connection.setter
    def connection(self, value):
        if isinstance(value, sqlite3.Connection):
            self._connection = value
        else:
            self._connection = sqlite3.connect(value) if value is not None else None
    
    @property 
    def memcon(self):
        if self._memcon is None:
            self._memcon = sqlite3.connect(':memory:')
        return self._memcon

    @memcon.setter
    def memcon(self, value):
        if isinstance(value, sqlite3.Connection):
            self._memcon = value
        else:
            self._memcon = sqlite3.connect(value) if value is not None else None

    def export_stock_to_sql(self):
        with self.memcon:
            cur = self.memcon.cursor()
            cur.execute(self.DROP_SQL_STRING.format(table=self.STOCK_TABLE))
            cur.execute(self.CREATE_SQL_STRING.format(table=self.STOCK_TABLE))
            cur.executemany(
                self.INSERT_SQL_STRING.format(table=self.STOCK_TABLE),
                self.create_stock_entries()
            )
            return '\n'.join(self.memcon.iterdump())


class PostgreSQLStockist(DatabaseStockist):

    INSERT_SQL_STRING = "INSERT INTO {table} VALUES (%s, %s, %s)"
    UPDATE_SQL_STRING = "UPDATE {table} set count=%s where pk=%s"
    DELETE_SQL_STRING = "DELETE FROM {table} WHERE pk=%s"

    def __init__(self, database=None, username=None, password=None):
        super(PostgreSQLStockist, self).__init__()
        if database is not None:
            self.connection = psycopg2.connect(
                database=database,
                user=username,
                password=password,
            )
    
    @property
    def connection(self):
        return super(PostgreSQLStockist, self).connection

    @connection.setter
    def connection(self, value):
        if isinstance(value, psycopg2.extensions.connection):
            self._connection = value
        elif value is None:
            self._connection = None
        else: 
            raise ValueError

    def new_connection(self, database, username=None, password=None):
        if self.connection is not None:
            self.connection.close()
        self.connection = psycopg2.connect(
            database=database_name,
            username=username,
            password=password
        )