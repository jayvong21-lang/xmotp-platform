import importlib
import os
import sqlite3
import tempfile
import unittest
import json


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
            db.execute('DROP INDEX IF EXISTS idx_listings_unit')
            values = ('思明区', '测试大厦', 100, '101', '2026-07-01 10:00:00')
            db.execute('INSERT INTO listings (district, building_name, area_m2, floor_info, updated_at) VALUES (?,?,?,?,?)', values)
            values = ('思明区', '测试大厦', 100, '101', '2026-07-02 10:00:00')
            db.execute('INSERT INTO listings (district, building_name, area_m2, floor_info, updated_at) VALUES (?,?,?,?,?)', values)
            values = ('思明区', '测试大厦', 100, '102', '2026-07-03 10:00:00')
            db.execute('INSERT INTO listings (district, building_name, area_m2, floor_info, updated_at) VALUES (?,?,?,?,?)', values)
            db.commit()

        self.module.init_db()

        with sqlite3.connect(self.db_path) as db:
            rows = db.execute("SELECT id, updated_at FROM listings WHERE building_name='测试大厦'").fetchall()
            archived = db.execute("SELECT original_id FROM listings_duplicates_archive WHERE building_name='测试大厦'").fetchall()
            indexes = db.execute("PRAGMA index_list('listings')").fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(archived), 1)
        self.assertIn('2026-07-02 10:00:00', [row[1] for row in rows])
        self.assertIn('2026-07-03 10:00:00', [row[1] for row in rows])
        self.assertTrue(any(row[1] == 'idx_listings_unit' and row[2] == 1 for row in indexes))

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

    def test_public_sync_only_exports_safe_active_fields(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("""INSERT INTO listings (
                district, building_name, area_m2, total_rent_month, property_fee,
                floor_info, decoration, parking, source, contact_name,
                contact_phone, notes, status
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                '思明区', '公开测试大厦', 100, 5000, 8, '10层', '精装', '有',
                '业主直租', '张先生', '13800138000', '看房密码1234', '在租'
            ))
            db.execute("""INSERT INTO listings (
                district, building_name, area_m2, notes, status
            ) VALUES (?,?,?,?,?)""", ('湖里区', '已下架大厦', 200, '内部信息', '已下架'))
            db.commit()

        output = os.path.join(self.temp_dir.name, 'properties-data.js')
        count = self.module.sync_public_properties(self.db_path, output)
        with open(output, encoding='utf-8') as handle:
            content = handle.read()
        payload = content.split('const propertiesList = ', 1)[1].split(';\n\nwindow.', 1)[0]
        data = json.loads(payload)

        self.assertEqual(count, 1)
        self.assertEqual(data[0]['district'], '思明')
        self.assertEqual(data[0]['unit_price_rent'], 50.0)
        self.assertNotIn('contact_phone', data[0])
        self.assertNotIn('contact_name', data[0])
        self.assertNotIn('source', data[0])
        self.assertNotIn('看房密码1234', content)
        self.assertNotIn('已下架大厦', content)


if __name__ == '__main__':
    unittest.main()
