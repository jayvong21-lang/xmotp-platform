#!/usr/bin/env python3
"""从 xmOTP 主库生成龙溪官网可公开的房源数据。"""
import argparse
import json
import os
import sqlite3
import tempfile


PUBLIC_QUERY = """
    SELECT id, district, building_name, area_m2, total_rent_month,
           property_fee, floor_info, decoration, parking
    FROM listings
    WHERE status = '在租'
    ORDER BY district, building_name, area_m2, id
"""


def _number(value):
    if value is None:
        return 0
    value = float(value)
    return int(value) if value.is_integer() else round(value, 3)


def build_public_properties(database):
    db = sqlite3.connect(database)
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute(PUBLIC_QUERY).fetchall()
    finally:
        db.close()

    properties = []
    for row in rows:
        area = _number(row['area_m2'])
        monthly_rent = _number(row['total_rent_month'])
        unit_price = round(float(monthly_rent) / float(area), 2) if area and monthly_rent else 0
        district = (row['district'] or '').strip()
        if district.endswith('区'):
            district = district[:-1]
        properties.append({
            'id': row['id'],
            'district': district,
            'building_name': (row['building_name'] or '').strip(),
            'area_m2': area,
            'total_rent_month': monthly_rent,
            'property_fee': _number(row['property_fee']),
            'floor_info': (row['floor_info'] or '').strip(),
            'decoration': (row['decoration'] or '').strip(),
            'parking': (row['parking'] or '').strip(),
            'lease_expiry': '',
            'unit_price_rent': unit_price,
            # 官网当前不展示备注；保持字段兼容，但绝不输出内部备注和看房密码。
            'notes': '',
        })
    return properties


def sync_public_properties(database, output):
    properties = build_public_properties(database)
    content = (
        '/**\n'
        ' * 龙溪企服 - 房源库公开数据（自动生成，请勿手工修改）\n'
        ' * 数据来源：xmOTP listings 表，仅同步“在租”房源。\n'
        ' * 联系人、电话、来源、内部备注和看房密码不会写入官网。\n'
        ' */\n\n'
        'const propertiesList = ' +
        json.dumps(properties, ensure_ascii=False, indent=2) +
        ';\n\nwindow.propertiesList = propertiesList;\n'
    )

    output = os.path.abspath(output)
    output_dir = os.path.dirname(output)
    if not os.path.isdir(output_dir):
        raise RuntimeError('官网数据目录不存在: ' + output_dir)
    fd, temp_path = tempfile.mkstemp(prefix='.properties-', suffix='.js', dir=output_dir)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(content)
        os.replace(temp_path, output)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise
    return len(properties)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    count = sync_public_properties(args.db, args.output)
    print('synced_properties={0}'.format(count))


if __name__ == '__main__':
    main()
