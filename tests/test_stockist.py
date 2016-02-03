import unittest
import mock
import collections
import sqlite3
import sys; sys.path.append(sys.path[0] + '/../')

import stockist as stockist_module


class TestStockist(unittest.TestCase):

    def setUp(self):
        self.stockist = stockist_module.Stockist()

    def test_lock(self):
        self.assertFalse(self.stockist.stock_locked)
        self.assertFalse(self.stockist.is_locked)
        self.stockist.lock_stock_list()
        self.assertTrue(self.stockist.stock_locked)
        self.assertTrue(self.stockist.is_locked)
        self.stockist.unlock_stock_list()
        self.assertFalse(self.stockist.stock_locked)
        self.assertFalse(self.stockist.is_locked)
        self.stockist.stock_locked = True
        self.assertTrue(self.stockist.stock_locked)
        self.assertTrue(self.stockist.is_locked)
        self.assertRaises(ValueError, setattr, self.stockist, "stock_locked", 'abc')
        self.assertRaises(ValueError, setattr, self.stockist, "stock_locked", None)
        self.assertEqual(self.stockist.stock_locked, self.stockist.is_locked)

    def test_locked_methods(self):
        self.stockist.stock_locked = True
        self.assertRaises(stockist_module.StockLockedError, self.stockist.__setitem__, 0, None)
        self.assertRaises(stockist_module.StockLockedError, self.stockist.__delitem__, 0)
        self.assertRaises(stockist_module.StockLockedError, self.stockist.delete_stock_entry, 0)
        self.assertRaises(stockist_module.StockLockedError, self.stockist.new_stock_item, None)

    def test_attributes(self):
        self.assertIsInstance(self.stockist.stock_locked, bool)
        self.assertIsInstance(self.stockist.stock, collections.OrderedDict)
        self.assertIsInstance(self.stockist.name_id_map, collections.OrderedDict)
        self.assertIsInstance(self.stockist.stock_ids, list)
        self.assertIsInstance(self.stockist.last_stock_id, int)
        self.assertIsInstance(self.stockist.stock_count, list)
        self.assertIsInstance(self.stockist.next_free_stock_id, int)


class TestDatabaseStockist(TestStockist):

    def setUp(self):
        self.stockist = stockist_module.DatabaseStockist()

    def test_locked_methods(self):
        super(TestDatabaseStockist, self).test_locked_methods()
        self.assertRaises(stockist_module.StockLockedError, self.stockist.update_stock_from_db)

    def test_attributes(self):
        super(TestDatabaseStockist, self).test_attributes()
        self.assertRaises(stockist_module.StockConnectionError, getattr, self.stockist, 'connection')
        self.stockist._connection = mock.MagicMock()
        self.assertIsInstance(self.stockist.is_database_up_to_date, bool)
        self.assertIsInstance(self.stockist.is_missing_stock_from_database, bool)
        self.assertIsInstance(self.stockist.database_stock, dict)      


class TestSQLiteStockist(TestDatabaseStockist):

    def setUp(self):
        self.stockist = stockist_module.SQLiteStockist()
    
    def test_attributes(self):
        super(TestSQLiteStockist, self).test_attributes()
        self.assertIsInstance(self.stockist.memcon, sqlite3.Connection)


class TestPostgreSQLStockist(TestDatabaseStockist):

    def setUp(self):
        self.stockist = stockist_module.PostgreSQLStockist()


if __name__ == '__main__':
    unittest.main()