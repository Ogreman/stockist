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

    def test_locked_method_wrapper(self):
        mocked_method = mock.Mock(return_value=None)
        wrapped_mock = stockist_module.locked_method(mocked_method)
        wrapped_mock(self.stockist)
        self.assertTrue(mocked_method.called)
        mocked_method.reset_mock()
        self.stockist.stock_locked = True
        self.assertRaises(stockist_module.StockLockedError, wrapped_mock, self.stockist)
        self.assertFalse(mocked_method.called)

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
        self.assertEqual(self.stockist.last_stock_id, None)
        self.assertEqual(self.stockist.last_stock_entry, None)
        self.assertIsInstance(self.stockist.stock_count, list)
        self.assertIsInstance(self.stockist.next_free_stock_id, int)

    def test_stock_ids_for_item(self):
        self.stockist.name_id_map['test'] = [(1, 'test_#1')]
        self.assertIsInstance(self.stockist.stock_ids_for_item(None), list)
        self.assertEqual(len(self.stockist.stock_ids_for_item(None)), 0)
        self.assertEqual(len(self.stockist.stock_ids_for_item(1)), 0)
        self.assertIn(1, self.stockist.stock_ids_for_item('test'))
        self.assertNotIn('test_#1', self.stockist.stock_ids_for_item('test'))
        self.assertEqual(len(self.stockist.stock_ids_for_item('test')), 1)
        self.stockist.name_id_map['test'].append((2, 'test_#2'))
        self.assertIn(1, self.stockist.stock_ids_for_item('test'))
        self.assertIn(2, self.stockist.stock_ids_for_item('test'))
        self.assertNotIn('test_#2', self.stockist.stock_ids_for_item('test'))
        self.assertEqual(len(self.stockist.stock_ids_for_item('test')), 2)
        self.assertEqual(len(self.stockist.stock_ids_for_item('fail')), 0)
        new_mock = mock.Mock(__str__= lambda _: "mock")
        self.stockist.name_id_map[str(new_mock)] = [(3, 'mock_#3')]
        self.assertIn(3, self.stockist.stock_ids_for_item(new_mock))
        self.assertEqual(len(self.stockist.stock_ids_for_item(new_mock)), 1)

    def test_stock_for_item(self):
        self.stockist.stock[1] = mock.MagicMock(name="test_#1")
        self.stockist.stock[2] = mock.MagicMock(name="test_#2")
        self.stockist.stock[3] = mock.MagicMock(name="test_#3")
        self.stockist.stock_ids_for_item = mock.Mock(return_value=[1, 2])

        self.assertIsInstance(self.stockist.stock_for_item(None), list)

        self.assertIn(self.stockist.stock[1], self.stockist.stock_for_item('test'))
        self.assertIn(self.stockist.stock[2], self.stockist.stock_for_item('test'))
        self.assertEqual(len(self.stockist.stock_for_item('test')), 2)
        
        new_mock = mock.Mock(__str__= lambda _: "mock")
        self.stockist.stock_ids_for_item.return_value = [3]
        self.assertIn(self.stockist.stock[3], self.stockist.stock_for_item(new_mock))
        self.assertEqual(len(self.stockist.stock_for_item(new_mock)), 1)
        self.assertTrue(self.stockist.stock_ids_for_item.called)

    def test___getitem__(self):
        self.stockist.stock[1] = mock.MagicMock(name="test_#1")
        self.assertEqual(self.stockist[1], self.stockist.stock[1])
        self.stockist.stock_for_item = mock.Mock(return_value=-123)
        self.assertEqual(self.stockist['test'], -123)
        self.assertTrue(self.stockist.stock_for_item.called)
        self.assertRaises(KeyError, self.stockist.__getitem__, 0)

    def test___setitem__(self):
        self.stockist.new_stock_item = mock.Mock()
        self.stockist[1] = 'test'
        self.stockist.new_stock_item.assert_called_with('test', new_id=1)
        self.stockist[None] = 'test'
        self.stockist.new_stock_item.assert_called_with('test')

    def test___delitem__(self):
        self.stockist.delete_stock_entry = mock.Mock()
        self.stockist.stock_ids_for_item = mock.Mock(return_value=[2])
        
        del self.stockist[1]
        self.stockist.delete_stock_entry.assert_called_with(1)
        
        del self.stockist['test']
        self.stockist.delete_stock_entry.assert_called_with(2)
        
    def test___contains__(self):
        old_method = collections.OrderedDict.__contains__
        # some dangerous monkey-patching going on right here...
        collections.OrderedDict.__contains__ = mock.Mock(return_value=1)

        self.assertTrue(1 in self.stockist)
        collections.OrderedDict.__contains__.assert_called_with(1)

        self.assertTrue('test' in self.stockist)
        collections.OrderedDict.__contains__.assert_called_with('test')

        # make sure we set it back otherwise all hell may break loose.
        collections.OrderedDict.__contains__ = old_method

    def test_stock_ids(self):
        self.stockist.stock.keys = mock.Mock()
        self.stockist.stock_ids
        self.assertTrue(self.stockist.stock.keys.called)

    def test_last_stock_id(self):
        self.stockist.stock.keys = mock.Mock(return_value=[1, 2, 3])
        self.assertEqual(self.stockist.last_stock_id, 3)
        self.stockist.stock.keys.return_value = []
        self.assertEqual(self.stockist.last_stock_id, None)

    def test_last_stock_entry(self):
        self.stockist.stock.values = mock.Mock(return_value=['a', 'b', 'c'])
        self.assertEqual(self.stockist.last_stock_entry, 'c')
        self.stockist.stock.values.return_value = []
        self.assertEqual(self.stockist.last_stock_id, None)

    def test_stock_count(self):
        self.stockist._stock = {1: {'count': 1}, 2: {}}
        self.assertEqual(len(self.stockist.stock_count), 2)
        self.assertEqual(len(self.stockist.stock_count[0]), 2)
        self.assertEqual(len(self.stockist.stock_count[1]), 2)
        self.assertIn((1,1), self.stockist.stock_count)
        self.assertIn((2,0), self.stockist.stock_count)

    def test_create_item_data(self):
        data = stockist_module.Stockist.create_item_data(0, 'test', 1)
        self.assertIn('stock_id', data)
        self.assertIn('unique_name', data)
        self.assertIn('count', data)
        self.assertEqual(data['stock_id'], 0)
        self.assertEqual(data['unique_name'], 'test_#0')
        self.assertEqual(data['count'], 1)

    def test_next_free_stock_id(self):
        self.assertEqual(self.stockist.next_free_stock_id, 0)
        self.stockist._stock[0] = {}
        self.assertEqual(self.stockist.next_free_stock_id, 1)
        for i in range(1, 100):
            self.stockist._stock[i] = {}
        self.assertEqual(self.stockist.next_free_stock_id, i + 1)
        self.stockist._stock[i * 100] = {}
        self.assertEqual(self.stockist.next_free_stock_id, i + 1)
        self.stockist._next_free_stock_id = 0
        self.assertEqual(self.stockist.next_free_stock_id, i + 1)

    def test_delete_stock_entry(self):
        self.stockist._stock = {1: {'unique_name': 'test_#1'}}
        self.stockist._name_id_map = {'test': set((1, 'test_#1'))}
        self.stockist.delete_stock_entry(1)
        self.assertNotIn(1, self.stockist._stock)
        self.assertNotIn((1, 'test_#1'), self.stockist._name_id_map)
        self.assertRaises(KeyError, self.stockist.delete_stock_entry, 255)

    def test_new_stock_item(self):
        pass

    def test_list_stocked_item_ids(self):
        pass

    def test_item_stocked(self):
        pass

    def test_last_stock_id_for_item(self):
        pass

    def test_last_stock_entry_for_item(self):
        pass

    def test_stock_item(self):
        pass

    def test_increase_stock(self):
        pass


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
   
    def test_delete_stock_entry(self):
        self.stockist._stock = {1: {'unique_name': 'test_#1'}}
        self.stockist._name_id_map = {'test': set((1, 'test_#1'))}
        self.assertIn(1, self.stockist._stock)
        self.stockist.delete_stock_entry(1, update_db=False)
        self.assertNotIn(1, self.stockist._stock)
        self.assertNotIn((1, 'test_#1'), self.stockist._name_id_map)

        self.assertRaises(KeyError, self.stockist.delete_stock_entry, 255, update_db=False)
        self.assertRaises(KeyError, self.stockist.delete_stock_entry, 256, update_db=True)
        
        self.stockist._stock = {2: {'unique_name': 'test_#2'}}
        self.stockist._name_id_map = {'test': set((2, 'test_#2'))}

        if self.stockist.DELETE_SQL_STRING is not None:
            with mock.patch('stockist.DatabaseStockist.connection') as con:
                cursor = mock.MagicMock(execute=mock.Mock())
                connection = mock.MagicMock(cursor=lambda: cursor, commit=mock.Mock())
                con.__enter__ = mock.Mock(return_value=connection)
                self.stockist.delete_stock_entry(2, update_db=True)

            self.assertNotIn(2, self.stockist._stock)
            self.assertNotIn((2, 'test_#1'), self.stockist._name_id_map)
            expected = self.stockist.DELETE_SQL_STRING.format(
                table=self.stockist.STOCK_TABLE
            )
            cursor.execute.assert_called_with(expected, (2,))
        else:
            self.assertRaises(NotImplementedError, self.stockist.delete_stock_entry, 2, update_db=True)
        
        self.assertNotIn(2, self.stockist._stock)
        self.assertNotIn((2, 'test_#2'), self.stockist._name_id_map)


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