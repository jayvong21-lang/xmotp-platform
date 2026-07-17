import importlib
import os
import sqlite3
import tempfile
import unittest


class XmotpAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.db_path = os.path.join(cls.temp_dir.name, 'test.db')
        os.environ['XMOTP_DATABASE'] = cls.db_path
        cls.module = importlib.import_module('app')
        cls.app = cls.module.app
        cls.app.config.update(TESTING=True, SECRET_KEY='test-key')

    @classmethod
    def tearDownClass(cls):
        os.environ.pop('XMOTP_DATABASE', None)
        cls.temp_dir.cleanup()

    def setUp(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute('DELETE FROM listings')
            db.commit()
        self.client = self.app.test_client()

    def login(self):
        return self.client.post('/login', data={'username': 'admin', 'password': 'admin123'})

    def test_normalize_row_accepts_chinese_and_english_headers(self):
        row = self.module.normalize_row({
            '楼盘': ' 软件园二期 ',
            'area_m2': 120,
            '月租': '12,000',
            '联系电话': 13800138000,
            '备注': None,
        })
        self.assertEqual(row['building_name'], '软件园二期')
        self.assertEqual(row['area_m2'], '120')
        self.assertEqual(self.module.number(row['total_rent_month']), 12000)
        self.assertEqual(row['contact_phone'], '13800138000')
        self.assertEqual(row['notes'], '')

    def test_init_db_deduplicates_and_creates_unique_index(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute('DROP INDEX IF EXISTS idx_listings_dedup')
            values = ('思明区', '测试大厦', 100, '2026-07-01 10:00:00')
            db.execute('INSERT INTO listings (district, building_name, area_m2, updated_at) VALUES (?,?,?,?)', values)
            values = ('思明区', '测试大厦', 100, '2026-07-02 10:00:00')
            db.execute('INSERT INTO listings (district, building_name, area_m2, updated_at) VALUES (?,?,?,?)', values)
            db.commit()

        self.module.init_db()

        with sqlite3.connect(self.db_path) as db:
            rows = db.execute("SELECT id, updated_at FROM listings WHERE building_name='测试大厦'").fetchall()
            archived = db.execute("SELECT original_id FROM listings_duplicates_archive WHERE building_name='测试大厦'").fetchall()
            indexes = db.execute("PRAGMA index_list('listings')").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(archived), 1)
        self.assertEqual(rows[0][1], '2026-07-02 10:00:00')
        self.assertTrue(any(row[1] == 'idx_listings_dedup' and row[2] == 1 for row in indexes))

    def test_api_requires_login_and_returns_data_after_login(self):
        response = self.client.get('/api/listings')
        self.assertEqual(response.status_code, 401)

        self.login()
        response = self.client.get('/api/listings?limit=10')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.get_json(), list)
        stats = self.client.get('/api/stats')
        self.assertEqual(stats.status_code, 200)
        self.assertIn('total', stats.get_json())


if __name__ == '__main__':
    unittest.main()
