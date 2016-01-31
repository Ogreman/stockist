# stock management (items, count, database)
# TODO: shopping cart (add item, remove item, checkout + remove from stock, api)
# TODO: payment collection (stripe)
import collections
import sqlite3


class StockError(Exception):
    pass


class StockLockedError(StockError):
    pass


class StockConnectionError(StockError):
    pass


class Stockist(object):

    def __init__(self):
        self.name_id_map = collections.OrderedDict()
        self.stock = collections.OrderedDict()
        self.__lock_items = False

    def lock_stock_list(self):
        self.__lock_items = True

    def unlock_stock_list(self):
        self.__lock_items = False

    @property
    def is_locked(self):
        return self.__lock_items

    def stock_ids_for_item(self, item):
        return [stock_id for stock_id, _ in self.name_id_map.get(str(item), [])]

    def stock_for_item(self, item):
        return [
            self.stock[stock_id]
            for stock_id in self.stock_ids_for_item(item)
        ]

    def __getitem__(self, item_or_stock_id):
        if isinstance(item_or_stock_id, int):
            return self.stock[item_or_stock_id]
        return self.stock_for_item(item_or_stock_id)

    def __setitem__(self, item_or_stock_id, item):
        if self.is_locked:
            raise StockLockedError
        else:
            if isinstance(item_or_stock_id, int):
                self.new_stock_item(item, new_id=item_or_stock_id)
            else:
                self.new_stock_item(item)

    def __delitem__(self, item_or_stock_id):
        if self.is_locked:
            raise StockLockedError
        if isinstance(item_or_stock_id, int):
            self.delete_stock_entry(item_or_stock_id)
        else:
            for stock_id in self.stock_ids_for_item(item_or_stock_id):
                self.delete_stock_entry(stock_id)

    @property
    def stock_ids(self):
        return self.stock.keys()

    @property 
    def last_stock_id(self):
        try:
            return self.stock.keys()[-1]
        except IndexError:
            return -1
    
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
            'item': item,
            'count': count,
        }

    @property 
    def next_free_stock_id(self):
        if not hasattr(self, '_next_free_stock_id'):
            self._next_free_stock_id = 0
        while self._next_free_stock_id in self.stock:
            self._next_free_stock_id += 1
        return self._next_free_stock_id

    def delete_stock_entry(self, old_id):
        if self.is_locked:
            raise StockLockedError
        data = self.stock[old_id]
        mapping_list = self.name_id_map[str(data['item'])]
        for index, mapping in enumerate(mapping_list):
            if old_id in mapping:
                mapping_list.pop(index)
        del self.stock[old_id]

    def new_stock_item(self, item, new_id=None, force=False):
        if self.is_locked:
            raise StockLockedError
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


class SQLiteStockist(Stockist):

    STOCK_TABLE = "stock"
    StockEntry = collections.namedtuple('StockEntry', ['pk', 'name', 'count'])

    def __init__(self, database_url=None):
        super(SQLiteStockist, self).__init__()
        self.connection = database_url
        self.memcon = sqlite3.connect(':memory:')

    @staticmethod
    def select(cur, table_name, what="*"):
        cur.execute("SELECT {0} FROM {1};".format(what, table_name))
        return cur.fetchall()

    @property
    def database_stock(self):
        with self.connection:
            self.connection.row_factory = sqlite3.Row
            cur = self.connection.cursor()
            return {
                row['pk']: {
                    'stock_id': row['pk'],
                    'unique_name': row['name'],
                    'item': None,
                    'count': row['count'],
                }
                for row in self.select(cur, self.STOCK_TABLE)
            }

    def retrieve_stock_from_db(self, force=False):
        if force or self.missing_stock_from_database:
            stock_data = self.database_stock
            for data in stock_data.values():
                item_name, _ = data['unique_name'].split('_#')
                existing_items = self.name_id_map.setdefault(item_name, set())
                existing_items.add((data['stock_id'], data['unique_name']))
            self.stock.update(stock_data)

    @property
    def connection(self):
        if self._connection is None:
            raise StockConnectionError('No database connection!')
        return self._connection
    
    @connection.setter
    def connection(self, value):
        if isinstance(value, sqlite3.Connection):
            self._connection = value
        else:
            self._connection = sqlite3.connect(value) if value is not None else None
    
    @property
    def database_up_to_date(self):
        with self.connection:
            self.connection.row_factory = sqlite3.Row
            cur = self.connection.cursor()
            keys = [
                row['pk'] 
                for row in self.select(cur, self.STOCK_TABLE)
            ]
        if self.stock and not keys:
            return False
        return all(key in keys for key in self.stock.keys())

    @property 
    def missing_stock_from_database(self):
        with self.connection:
            self.connection.row_factory = sqlite3.Row
            cur = self.connection.cursor()
            keys = [
                row['pk'] 
                for row in self.select(cur, self.STOCK_TABLE)
            ]
        if keys and not self.stock:
            return True
        return not(all(key in self.stock.keys() for key in keys))

    def export_stock_to_sql(self):
        with self.memcon:
            cur = self.memcon.cursor()
            cur.execute("DROP TABLE IF EXISTS {table}"
                .format(table=self.STOCK_TABLE)
            )
            cur.execute(
                "CREATE TABLE {table}(pk INT, name TEXT, count INT)"
                .format(table=self.STOCK_TABLE)
            )
            cur.executemany(
                "INSERT INTO {table} VALUES(?, ?, ?)"
                .format(table=self.STOCK_TABLE),
                self.create_stock_entries()
            )
            return '\n'.join(self.memcon.iterdump())

    def dump_stock_to_database(self):
        with self.connection as connection:
            connection.execute("DROP TABLE IF EXISTS {table}"
                .format(table=self.STOCK_TABLE)
            )
            connection.execute(
                "CREATE TABLE {table}(pk INT, name TEXT, count INT)"
                .format(table=self.STOCK_TABLE)
            )
            connection.executemany(
                "INSERT INTO {table} VALUES(?, ?, ?)"
                .format(table=self.STOCK_TABLE),
                self.create_stock_entries()
            )
            connection.commit()

    def reset_database(self):
        with self.connection as connection:
            connection.execute("DROP TABLE IF EXISTS {table}"
                .format(table=self.STOCK_TABLE)
            )
            connection.execute(
                "CREATE TABLE {table}(pk INT, name TEXT, count INT)"
                .format(table=self.STOCK_TABLE)
            )
            connection.commit()

    def create_database(self):
        with self.connection as connection:
            connection.execute(
                "CREATE TABLE {table}(pk INT, name TEXT, count INT)"
                .format(table=self.STOCK_TABLE)
            )
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
            connection.executemany(
                "INSERT INTO {table} VALUES(?, ?, ?)"
                .format(table=self.STOCK_TABLE),
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
        new_id = super(SQLiteStockist, self).new_stock_item(item, new_id, force)
        if update_db:
            with self.connection as connection:
                connection.execute(
                    "INSERT INTO {table} VALUES(?, ?, ?)"
                    .format(table=self.STOCK_TABLE),
                    self.create_stock_entry(new_id)
                )
                connection.commit()
        return new_id

    def delete_stock_entry(self, old_id, update_db=True):
        super(SQLiteStockist, self).delete_stock_entry(old_id)
        if update_db:
            with self.connection as connection:
                connection.execute(
                    "DELETE FROM {table} WHERE pk={id}"
                    .format(
                        table=self.STOCK_TABLE, 
                        id=old_id
                    )
                )
                connection.commit()

    def increase_stock(self, stock_id, amount=1, update_db=True):
        super(SQLiteStockist, self).increase_stock(stock_id, amount)
        if update_db:
            with self.connection as connection:
                connection.execute(
                    "UPDATE {table} set count={amount} where pk={id}"
                    .format(
                        table=self.STOCK_TABLE,
                        id=stock_id,
                        amount=self.stock[stock_id]['count']
                    )
                )
                connection.commit()


class Item(object):

    def __init__(self, identifier):
        self.identifier = identifier

    def __str__(self):
        return str(self.identifier)