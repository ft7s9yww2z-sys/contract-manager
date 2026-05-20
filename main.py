#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合同管理系统 - v4.0
功能：合同录入、开票回款、统计分析、图表展示、销售人员、搜索排序、到期预警、应收账款催款
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import DateEntry
import sqlite3
import os
import sys
from datetime import datetime, timedelta
import csv
import json
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 数据库路径 - 使用用户数据目录确保数据持久化
if sys.platform == 'win32':
    DATA_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'ContractManager')
else:
    DATA_DIR = os.path.join(os.path.expanduser('~'), '.contract_manager')

os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, 'contracts.db')


class DatabaseManager:
    """数据库管理"""
    
    def __init__(self):
        self.init_database()
    
    def get_connection(self):
        return sqlite3.connect(DB_PATH)
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 检查是否需要升级数据库
        cursor.execute("PRAGMA table_info(contracts)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if not columns:
            cursor.execute('''
                CREATE TABLE contracts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    合同编号 TEXT UNIQUE NOT NULL,
                    项目代码 TEXT,
                    合同名称 TEXT,
                    对方单位名称 TEXT,
                    区域 TEXT,
                    合同金额 REAL,
                    实际签约日期 TEXT,
                    合同起始日期 TEXT,
                    合同终止日期 TEXT,
                    合同内容 TEXT,
                    销售人员 TEXT,
                    催款状态 TEXT DEFAULT '未催款',
                    催款日期 TEXT,
                    催款备注 TEXT,
                    创建时间 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        else:
            # 升级数据库
            if '合同名称' not in columns:
                cursor.execute('ALTER TABLE contracts ADD COLUMN 合同名称 TEXT')
            if '实际签约日期' not in columns:
                cursor.execute('ALTER TABLE contracts ADD COLUMN 实际签约日期 TEXT')
            if '销售人员' not in columns:
                cursor.execute('ALTER TABLE contracts ADD COLUMN 销售人员 TEXT')
            if '催款状态' not in columns:
                cursor.execute('ALTER TABLE contracts ADD COLUMN 催款状态 TEXT DEFAULT \'未催款\'')
            if '催款日期' not in columns:
                cursor.execute('ALTER TABLE contracts ADD COLUMN 催款日期 TEXT')
            if '催款备注' not in columns:
                cursor.execute('ALTER TABLE contracts ADD COLUMN 催款备注 TEXT')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                合同编号 TEXT NOT NULL,
                开票日期 TEXT,
                开票金额 REAL,
                FOREIGN KEY (合同编号) REFERENCES contracts(合同编号)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                合同编号 TEXT NOT NULL,
                回款日期 TEXT,
                回款金额 REAL,
                FOREIGN KEY (合同编号) REFERENCES contracts(合同编号)
            )
        ''')
        
        # 催款记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collection_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                合同编号 TEXT NOT NULL,
                催款日期 TEXT,
                催款方式 TEXT,
                联系人 TEXT,
                催款内容 TEXT,
                对方反馈 TEXT,
                催款结果 TEXT,
                FOREIGN KEY (合同编号) REFERENCES contracts(合同编号)
            )
        ''')
        
        # 销售人员表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS salespersons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                姓名 TEXT UNIQUE NOT NULL,
                联系方式 TEXT,
                备注 TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_salespersons(self):
        """获取所有销售人员列表"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT 姓名 FROM salespersons ORDER BY 姓名')
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]
    
    def add_salesperson(self, name, phone='', note=''):
        """添加销售人员"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO salespersons (姓名, 联系方式, 备注) VALUES (?, ?, ?)',
                          (name, phone, note))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def add_contract(self, data):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO contracts 
                (合同编号, 项目代码, 合同名称, 对方单位名称, 区域, 合同金额, 
                 实际签约日期, 合同起始日期, 合同终止日期, 合同内容, 销售人员)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (data['合同编号'], data['项目代码'], data['合同名称'],
                  data['对方单位名称'], data['区域'], data['合同金额'],
                  data['实际签约日期'], data['合同起始日期'], 
                  data['合同终止日期'], data['合同内容'], data.get('销售人员', '')))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def update_contract(self, contract_no, data):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE contracts SET 
                项目代码=?, 合同名称=?, 对方单位名称=?, 区域=?, 合同金额=?,
                实际签约日期=?, 合同起始日期=?, 合同终止日期=?, 合同内容=?, 销售人员=?
                WHERE 合同编号=?
            ''', (data['项目代码'], data['合同名称'], data['对方单位名称'],
                  data['区域'], data['合同金额'], data['实际签约日期'],
                  data['合同起始日期'], data['合同终止日期'], 
                  data['合同内容'], data.get('销售人员', ''), contract_no))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def update_collection_status(self, contract_no, status, date='', note=''):
        """更新催款状态"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE contracts SET 催款状态=?, 催款日期=?, 催款备注=?
            WHERE 合同编号=?
        ''', (status, date, note, contract_no))
        conn.commit()
        conn.close()
    
    def get_contract_by_no(self, contract_no):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM contracts WHERE 合同编号=?', (contract_no,))
        row = cursor.fetchone()
        conn.close()
        return row
    
    def delete_contract(self, contract_no):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM invoices WHERE 合同编号=?', (contract_no,))
            cursor.execute('DELETE FROM payments WHERE 合同编号=?', (contract_no,))
            cursor.execute('DELETE FROM collection_records WHERE 合同编号=?', (contract_no,))
            cursor.execute('DELETE FROM contracts WHERE 合同编号=?', (contract_no,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def get_contracts(self, year=None, region=None, salesperson=None, search_text=None):
        conn = self.get_connection()
        query = '''
            SELECT 
                c.合同编号, c.项目代码, c.合同名称, c.对方单位名称, c.区域, c.合同金额,
                c.实际签约日期, c.合同起始日期, c.合同终止日期, c.合同内容, c.销售人员,
                c.催款状态, c.催款日期,
                COALESCE(SUM(i.开票金额), 0) as 累计开票,
                COALESCE(SUM(p.回款金额), 0) as 累计回款
            FROM contracts c
            LEFT JOIN invoices i ON c.合同编号 = i.合同编号
            LEFT JOIN payments p ON c.合同编号 = p.合同编号
        '''
        
        conditions = []
        params = []
        
        if year:
            conditions.append("strftime('%Y', c.实际签约日期) = ?")
            params.append(str(year))
        if region:
            conditions.append("c.区域 = ?")
            params.append(region)
        if salesperson:
            conditions.append("c.销售人员 = ?")
            params.append(salesperson)
        if search_text:
            conditions.append('''(
                c.合同编号 LIKE ? OR 
                c.项目代码 LIKE ? OR 
                c.合同名称 LIKE ? OR 
                c.对方单位名称 LIKE ? OR
                c.销售人员 LIKE ?
            )''')
            search_pattern = f'%{search_text}%'
            params.extend([search_pattern] * 5)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " GROUP BY c.合同编号 ORDER BY c.创建时间 DESC"
        
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def get_expiring_contracts(self, days=30):
        """获取即将到期的合同"""
        conn = self.get_connection()
        today = datetime.now().strftime('%Y-%m-%d')
        future = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        
        query = '''
            SELECT 
                c.合同编号, c.项目代码, c.合同名称, c.对方单位名称, c.区域, c.合同金额,
                c.实际签约日期, c.合同起始日期, c.合同终止日期, c.合同内容, c.销售人员,
                COALESCE(SUM(i.开票金额), 0) as 累计开票,
                COALESCE(SUM(p.回款金额), 0) as 累计回款
            FROM contracts c
            LEFT JOIN invoices i ON c.合同编号 = i.合同编号
            LEFT JOIN payments p ON c.合同编号 = p.合同编号
            WHERE c.合同终止日期 >= ? AND c.合同终止日期 <= ?
            GROUP BY c.合同编号
            ORDER BY c.合同终止日期 ASC
        '''
        
        cursor = conn.cursor()
        cursor.execute(query, (today, future))
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def get_expired_contracts(self):
        """获取已到期的合同"""
        conn = self.get_connection()
        today = datetime.now().strftime('%Y-%m-%d')
        
        query = '''
            SELECT 
                c.合同编号, c.项目代码, c.合同名称, c.对方单位名称, c.区域, c.合同金额,
                c.实际签约日期, c.合同起始日期, c.合同终止日期, c.合同内容, c.销售人员,
                COALESCE(SUM(i.开票金额), 0) as 累计开票,
                COALESCE(SUM(p.回款金额), 0) as 累计回款
            FROM contracts c
            LEFT JOIN invoices i ON c.合同编号 = i.合同编号
            LEFT JOIN payments p ON c.合同编号 = p.合同编号
            WHERE c.合同终止日期 < ?
            GROUP BY c.合同编号
            ORDER BY c.合同终止日期 DESC
        '''
        
        cursor = conn.cursor()
        cursor.execute(query, (today,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def get_receivables_by_year(self, year):
        """获取指定年份的应收账款"""
        conn = self.get_connection()
        query = '''
            SELECT 
                c.合同编号, c.项目代码, c.合同名称, c.对方单位名称, c.区域, c.合同金额,
                c.实际签约日期, c.合同终止日期, c.销售人员, c.催款状态, c.催款日期, c.催款备注,
                COALESCE(SUM(i.开票金额), 0) as 累计开票,
                COALESCE(SUM(p.回款金额), 0) as 累计回款
            FROM contracts c
            LEFT JOIN invoices i ON c.合同编号 = i.合同编号
            LEFT JOIN payments p ON c.合同编号 = p.合同编号
            WHERE strftime('%Y', c.实际签约日期) = ?
            GROUP BY c.合同编号
            HAVING 累计开票 > 累计回款
            ORDER BY c.实际签约日期 DESC
        '''
        
        cursor = conn.cursor()
        cursor.execute(query, (str(year),))
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def get_years_with_receivables(self):
        """获取有应收账款的年份列表"""
        conn = self.get_connection()
        query = '''
            SELECT DISTINCT strftime('%Y', c.实际签约日期) as 年度
            FROM contracts c
            LEFT JOIN invoices i ON c.合同编号 = i.合同编号
            LEFT JOIN payments p ON c.合同编号 = p.合同编号
            WHERE c.实际签约日期 IS NOT NULL AND c.实际签约日期 != ''
            GROUP BY c.合同编号
            HAVING COALESCE(SUM(i.开票金额), 0) > COALESCE(SUM(p.回款金额), 0)
            ORDER BY 年度 DESC
        '''
        
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows if row[0]]
    
    def add_collection_record(self, contract_no, date, method, contact, content, feedback, result):
        """添加催款记录"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO collection_records 
            (合同编号, 催款日期, 催款方式, 联系人, 催款内容, 对方反馈, 催款结果)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (contract_no, date, method, contact, content, feedback, result))
        conn.commit()
        conn.close()
    
    def get_collection_records(self, contract_no):
        """获取合同的催款记录"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 催款日期, 催款方式, 联系人, 催款内容, 对方反馈, 催款结果
            FROM collection_records
            WHERE 合同编号 = ?
            ORDER BY 催款日期 DESC
        ''', (contract_no,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def add_invoice(self, contract_no, date, amount):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO invoices (合同编号, 开票日期, 开票金额) VALUES (?, ?, ?)',
                      (contract_no, date, amount))
        conn.commit()
        conn.close()
    
    def add_payment(self, contract_no, date, amount):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO payments (合同编号, 回款日期, 回款金额) VALUES (?, ?, ?)',
                      (contract_no, date, amount))
        conn.commit()
        conn.close()
    
    def get_yearly_stats(self):
        conn = self.get_connection()
        query = '''
            SELECT 
                strftime('%Y', c.实际签约日期) as 年度,
                COUNT(c.合同编号) as 合同数,
                SUM(c.合同金额) as 合同总额,
                COALESCE(SUM(i.开票金额), 0) as 开票总额,
                COALESCE(SUM(p.回款金额), 0) as 回款总额
            FROM contracts c
            LEFT JOIN invoices i ON c.合同编号 = i.合同编号
            LEFT JOIN payments p ON c.合同编号 = p.合同编号
            WHERE c.实际签约日期 IS NOT NULL AND c.实际签约日期 != ''
            GROUP BY strftime('%Y', c.实际签约日期)
            ORDER BY 年度 DESC
        '''
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def get_region_stats(self, year=None):
        conn = self.get_connection()
        query = '''
            SELECT 
                c.区域,
                strftime('%Y', c.实际签约日期) as 年度,
                c.合同内容,
                COUNT(c.合同编号) as 合同数,
                SUM(c.合同金额) as 合同总额,
                COALESCE(SUM(i.开票金额), 0) as 开票总额,
                COALESCE(SUM(p.回款金额), 0) as 回款总额
            FROM contracts c
            LEFT JOIN invoices i ON c.合同编号 = i.合同编号
            LEFT JOIN payments p ON c.合同编号 = p.合同编号
            WHERE c.实际签约日期 IS NOT NULL AND c.实际签约日期 != ''
        '''
        
        params = []
        if year:
            query += " AND strftime('%Y', c.实际签约日期) = ?"
            params.append(str(year))
        
        query += " GROUP BY c.区域, strftime('%Y', c.实际签约日期), c.合同内容 ORDER BY 年度 DESC, 区域"
        
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def get_salesperson_stats(self, year=None):
        """获取销售人员统计"""
        conn = self.get_connection()
        query = '''
            SELECT 
                c.销售人员,
                COUNT(c.合同编号) as 合同数,
                SUM(c.合同金额) as 合同总额,
                COALESCE(SUM(i.开票金额), 0) as 开票总额,
                COALESCE(SUM(p.回款金额), 0) as 回款总额
            FROM contracts c
            LEFT JOIN invoices i ON c.合同编号 = i.合同编号
            LEFT JOIN payments p ON c.合同编号 = p.合同编号
            WHERE c.实际签约日期 IS NOT NULL AND c.实际签约日期 != ''
        '''
        
        params = []
        if year:
            query += " AND strftime('%Y', c.实际签约日期) = ?"
            params.append(str(year))
        
        query += " GROUP BY c.销售人员 ORDER BY 合同总额 DESC"
        
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def import_from_file(self, file_path):
        count = 0
        try:
            if file_path.endswith(('.xlsx', '.xls')):
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(file_path, data_only=True)
                    
                    for sheet_name in wb.sheetnames:
                        ws = wb[sheet_name]
                        
                        headers = []
                        for cell in ws[1]:
                            headers.append(str(cell.value) if cell.value else '')
                        
                        for row in ws.iter_rows(min_row=2, values_only=True):
                            if not row[0]:
                                continue
                            
                            row_data = {}
                            for i, header in enumerate(headers):
                                if i < len(row):
                                    row_data[header] = row[i]
                            
                            data = {
                                '合同编号': str(row_data.get('合同编号', '') or ''),
                                '项目代码': str(row_data.get('项目代码', '') or ''),
                                '合同名称': str(row_data.get('合同名称', '') or ''),
                                '对方单位名称': str(row_data.get('对方单位名称', '') or ''),
                                '区域': str(row_data.get('区域', '') or ''),
                                '合同金额': float(row_data.get('合同金额', 0) or row_data.get('合同额', 0) or 0),
                                '实际签约日期': self._format_date(row_data.get('实际签约日期') or row_data.get('合同签字日期')),
                                '合同起始日期': self._format_date(row_data.get('合同起始日期')),
                                '合同终止日期': self._format_date(row_data.get('合同终止日期')),
                                '合同内容': str(row_data.get('合同内容', '') or row_data.get('合同内容（发生项目）', '') or ''),
                                '销售人员': str(row_data.get('销售人员', '') or '')
                            }
                            
                            if data['合同编号'] and data['合同编号'] != 'None':
                                if self.add_contract(data):
                                    count += 1
                    
                    wb.close()
                    
                except ImportError:
                    raise Exception("需要安装 openpyxl 库来读取 Excel 文件")
            else:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        data = {
                            '合同编号': row.get('合同编号', ''),
                            '项目代码': row.get('项目代码', ''),
                            '合同名称': row.get('合同名称', ''),
                            '对方单位名称': row.get('对方单位名称', ''),
                            '区域': row.get('区域', ''),
                            '合同金额': float(row.get('合同金额', 0) or 0),
                            '实际签约日期': row.get('实际签约日期', ''),
                            '合同起始日期': row.get('合同起始日期', ''),
                            '合同终止日期': row.get('合同终止日期', ''),
                            '合同内容': row.get('合同内容', ''),
                            '销售人员': row.get('销售人员', '')
                        }
                        if data['合同编号'] and self.add_contract(data):
                            count += 1
            
            return count
        except Exception as e:
            raise e
    
    def _format_date(self, date_value):
        if not date_value:
            return ''
        
        if hasattr(date_value, 'strftime'):
            return date_value.strftime('%Y-%m-%d')
        
        date_str = str(date_value)
        if date_str == 'None' or not date_str.strip():
            return ''
        
        try:
            from datetime import datetime as dt
            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%Y年%m月%d日']:
                try:
                    parsed = dt.strptime(date_str.strip(), fmt)
                    return parsed.strftime('%Y-%m-%d')
                except:
                    continue
            return date_str
        except:
            return date_str


class ContractManagerApp:
    """主应用"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("合同管理系统 v4.0")
        self.root.geometry("1500x850")
        
        self.db = DatabaseManager()
        
        self.regions = ['北方区', '西北区', '华东区', '华南区', '国际部', '其他']
        self.contract_types = ['维保费', '维修费', '技术服务费', '其他']
        self.collection_status = ['未催款', '催款中', '已承诺付款', '已回款', '坏账']
        self.collection_methods = ['电话', '邮件', '上门', '微信', '其他']
        
        self.sort_column = None
        self.sort_reverse = False
        
        self.create_widgets()
        self.load_data()
        self.check_expiring_contracts()
    
    def create_widgets(self):
        # 创建菜单栏
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # 数据菜单
        data_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="数据", menu=data_menu)
        data_menu.add_command(label="备份数据库", command=self.backup_database)
        data_menu.add_command(label="恢复数据库", command=self.restore_database)
        data_menu.add_separator()
        data_menu.add_command(label="导出Excel", command=self.export_to_excel)
        
        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self.show_about)
        
        # 创建主标签页
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # 合同管理
        contract_frame = ttk.Frame(notebook)
        notebook.add(contract_frame, text='合同管理')
        self.create_contract_tab(contract_frame)
        
        # 到期预警
        warning_frame = ttk.Frame(notebook)
        notebook.add(warning_frame, text='到期预警')
        self.create_warning_tab(warning_frame)
        
        # 应收账款
        receivable_frame = ttk.Frame(notebook)
        notebook.add(receivable_frame, text='应收账款')
        self.create_receivable_tab(receivable_frame)
        
        # 年度统计
        yearly_frame = ttk.Frame(notebook)
        notebook.add(yearly_frame, text='年度统计')
        self.create_yearly_tab(yearly_frame)
        
        # 区域统计
        region_frame = ttk.Frame(notebook)
        notebook.add(region_frame, text='区域统计')
        self.create_region_tab(region_frame)
        
        # 销售人员统计
        sales_frame = ttk.Frame(notebook)
        notebook.add(sales_frame, text='销售人员统计')
        self.create_salesperson_tab(sales_frame)
    
    def create_contract_tab(self, parent):
        # 工具栏
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(toolbar, text="添加合同", command=self.add_contract).pack(side='left', padx=2)
        ttk.Button(toolbar, text="修改合同", command=self.edit_contract).pack(side='left', padx=2)
        ttk.Button(toolbar, text="删除合同", command=self.delete_contract).pack(side='left', padx=2)
        ttk.Button(toolbar, text="添加开票", command=self.add_invoice).pack(side='left', padx=2)
        ttk.Button(toolbar, text="添加回款", command=self.add_payment).pack(side='left', padx=2)
        ttk.Button(toolbar, text="导入数据", command=self.import_data).pack(side='left', padx=2)
        ttk.Button(toolbar, text="刷新", command=self.load_data).pack(side='left', padx=2)
        
        # 搜索和筛选栏
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(filter_frame, text="搜索:").pack(side='left', padx=2)
        self.search_entry = ttk.Entry(filter_frame, width=20)
        self.search_entry.pack(side='left', padx=2)
        self.search_entry.bind('<Return>', lambda e: self.load_data())
        ttk.Button(filter_frame, text="搜索", command=self.load_data).pack(side='left', padx=2)
        ttk.Button(filter_frame, text="清除", command=self.clear_search).pack(side='left', padx=2)
        
        ttk.Separator(filter_frame, orient='vertical').pack(side='left', padx=10, fill='y')
        
        ttk.Label(filter_frame, text="年度:").pack(side='left', padx=2)
        self.year_filter = ttk.Combobox(filter_frame, width=10, state='readonly')
        self.year_filter['values'] = ['全部'] + [str(y) for y in range(2030, 2019, -1)]
        self.year_filter.set('全部')
        self.year_filter.pack(side='left', padx=2)
        self.year_filter.bind('<<ComboboxSelected>>', lambda e: self.load_data())
        
        ttk.Label(filter_frame, text="区域:").pack(side='left', padx=2)
        self.region_filter = ttk.Combobox(filter_frame, width=12, state='readonly')
        self.region_filter['values'] = ['全部'] + self.regions
        self.region_filter.set('全部')
        self.region_filter.pack(side='left', padx=2)
        self.region_filter.bind('<<ComboboxSelected>>', lambda e: self.load_data())
        
        ttk.Label(filter_frame, text="销售人员:").pack(side='left', padx=2)
        self.salesperson_filter = ttk.Combobox(filter_frame, width=12, state='readonly')
        self.update_salesperson_filter()
        self.salesperson_filter.pack(side='left', padx=2)
        self.salesperson_filter.bind('<<ComboboxSelected>>', lambda e: self.load_data())
        
        # 合同列表
        columns = ('合同编号', '项目代码', '合同名称', '对方单位', '区域', '销售人员', '合同金额', 
                  '签约日期', '起始日期', '终止日期', '合同内容', '累计开票', '累计回款', '应收账款')
        self.contract_tree = ttk.Treeview(parent, columns=columns, show='headings', height=25)
        
        # 设置列标题和宽度
        column_widths = {
            '合同编号': 120, '项目代码': 100, '合同名称': 150, '对方单位': 150,
            '区域': 80, '销售人员': 80, '合同金额': 120, '签约日期': 100,
            '起始日期': 100, '终止日期': 100, '合同内容': 100,
            '累计开票': 120, '累计回款': 120, '应收账款': 120
        }
        
        for col in columns:
            self.contract_tree.heading(col, text=col, command=lambda c=col: self.sort_by_column(c))
            self.contract_tree.column(col, width=column_widths.get(col, 100), anchor='center')
        
        # 滚动条
        scrollbar_y = ttk.Scrollbar(parent, orient='vertical', command=self.contract_tree.yview)
        scrollbar_x = ttk.Scrollbar(parent, orient='horizontal', command=self.contract_tree.xview)
        self.contract_tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        self.contract_tree.pack(side='left', fill='both', expand=True, padx=5)
        scrollbar_y.pack(side='right', fill='y', pady=5)
    
    def create_warning_tab(self, parent):
        # 工具栏
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(toolbar, text="刷新", command=self.load_warning_data).pack(side='left', padx=2)
        ttk.Button(toolbar, text="导出预警列表", command=self.export_warning_list).pack(side='left', padx=2)
        
        # 说明
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(info_frame, text="预警说明：", font=('Arial', 10, 'bold')).pack(side='left')
        ttk.Label(info_frame, text="黄色 - 30天内到期  |  橙色 - 已到期0-30天  |  红色 - 超期30天以上", 
                 foreground='gray').pack(side='left', padx=10)
        
        # 预警列表
        columns = ('合同编号', '合同名称', '对方单位', '区域', '销售人员', '合同金额',
                  '终止日期', '剩余天数', '累计开票', '累计回款', '应收账款')
        self.warning_tree = ttk.Treeview(parent, columns=columns, show='headings', height=30)
        
        column_widths = {
            '合同编号': 120, '合同名称': 150, '对方单位': 150, '区域': 80,
            '销售人员': 80, '合同金额': 120, '终止日期': 100, '剩余天数': 80,
            '累计开票': 120, '累计回款': 120, '应收账款': 120
        }
        
        for col in columns:
            self.warning_tree.heading(col, text=col)
            self.warning_tree.column(col, width=column_widths.get(col, 100), anchor='center')
        
        # 配置标签颜色
        self.warning_tree.tag_configure('warning_yellow', background='#FFF3CD')
        self.warning_tree.tag_configure('warning_orange', background='#FFE5B4')
        self.warning_tree.tag_configure('warning_red', background='#FFCCCC')
        
        scrollbar = ttk.Scrollbar(parent, orient='vertical', command=self.warning_tree.yview)
        self.warning_tree.configure(yscrollcommand=scrollbar.set)
        
        self.warning_tree.pack(side='left', fill='both', expand=True, padx=5)
        scrollbar.pack(side='right', fill='y', pady=5)
    
    def create_receivable_tab(self, parent):
        # 年份选择器
        year_frame = ttk.Frame(parent)
        year_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(year_frame, text="选择年份:").pack(side='left', padx=5)
        
        # 创建年份Notebook
        self.receivable_notebook = ttk.Notebook(parent)
        self.receivable_notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # 初始加载
        self.load_receivable_tabs()
    
    def load_receivable_tabs(self):
        """加载应收账款的年份标签页"""
        # 清除现有标签页
        for tab in self.receivable_notebook.tabs():
            self.receivable_notebook.forget(tab)
        
        # 获取有应收账款的年份
        years = self.db.get_years_with_receivables()
        
        if not years:
            # 显示提示
            empty_frame = ttk.Frame(self.receivable_notebook)
            self.receivable_notebook.add(empty_frame, text='暂无数据')
            ttk.Label(empty_frame, text="当前没有应收账款数据", font=('Arial', 14)).pack(pady=50)
            return
        
        # 为每个年份创建标签页
        for year in years:
            year_frame = ttk.Frame(self.receivable_notebook)
            self.receivable_notebook.add(year_frame, text=f'{year}年')
            self.create_receivable_year_tab(year_frame, year)
    
    def create_receivable_year_tab(self, parent, year):
        """创建指定年份的应收账款标签页"""
        # 工具栏
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(toolbar, text="刷新", command=lambda: self.load_receivable_data(parent, year)).pack(side='left', padx=2)
        ttk.Button(toolbar, text="导出Excel", command=lambda: self.export_receivable_excel(year)).pack(side='left', padx=2)
        
        # 账龄分析
        aging_frame = ttk.LabelFrame(parent, text="账龄分析")
        aging_frame.pack(fill='x', padx=5, pady=5)
        
        self.aging_labels = {}
        aging_periods = ['30天内', '31-60天', '61-90天', '91-180天', '180天以上']
        
        for i, period in enumerate(aging_periods):
            ttk.Label(aging_frame, text=f"{period}:").grid(row=0, column=i*2, padx=10, pady=5)
            self.aging_labels[period] = ttk.Label(aging_frame, text="0.00 元", font=('Arial', 10, 'bold'))
            self.aging_labels[period].grid(row=0, column=i*2+1, padx=5, pady=5)
        
        # 应收账款列表
        columns = ('合同编号', '合同名称', '对方单位', '区域', '销售人员', '合同金额',
                  '签约日期', '账龄(天)', '累计开票', '累计回款', '应收金额', '催款状态', '操作')
        
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)
        
        column_widths = {
            '合同编号': 120, '合同名称': 150, '对方单位': 150, '区域': 80,
            '销售人员': 80, '合同金额': 120, '签约日期': 100, '账龄(天)': 80,
            '累计开票': 120, '累计回款': 120, '应收金额': 120, '催款状态': 100, '操作': 100
        }
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=column_widths.get(col, 100), anchor='center')
        
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # 保存tree引用
        if not hasattr(self, 'receivable_trees'):
            self.receivable_trees = {}
        self.receivable_trees[year] = tree
        
        # 加载数据
        self.load_receivable_data(parent, year)
    
    def load_receivable_data(self, parent, year):
        """加载指定年份的应收账款数据"""
        if year not in self.receivable_trees:
            return
        
        tree = self.receivable_trees[year]
        
        # 清除现有数据
        for item in tree.get_children():
            tree.delete(item)
        
        # 获取数据
        rows = self.db.get_receivables_by_year(year)
        
        today = datetime.now()
        aging_data = {'30天内': 0, '31-60天': 0, '61-90天': 0, '91-180天': 0, '180天以上': 0}
        
        for row in rows:
            contract_no, project_code, contract_name, company, region, amount, \
            sign_date, end_date, salesperson, collection_status, collection_date, collection_note, \
            invoice, payment = row
            
            receivable = invoice - payment
            
            # 计算账龄
            aging_days = 0
            if sign_date:
                try:
                    sign_dt = datetime.strptime(sign_date, '%Y-%m-%d')
                    aging_days = (today - sign_dt).days
                except:
                    pass
            
            # 账龄分组
            if aging_days <= 30:
                aging_data['30天内'] += receivable
            elif aging_days <= 60:
                aging_data['31-60天'] += receivable
            elif aging_days <= 90:
                aging_data['61-90天'] += receivable
            elif aging_days <= 180:
                aging_data['91-180天'] += receivable
            else:
                aging_data['180天以上'] += receivable
            
            # 插入数据
            item_id = tree.insert('', 'end', values=(
                contract_no, contract_name or '', company, region, salesperson or '',
                f'{amount:,.2f}' if amount else '0.00',
                sign_date or '', aging_days,
                f'{invoice:,.2f}', f'{payment:,.2f}', f'{receivable:,.2f}',
                collection_status or '未催款', '操作'
            ))
            
            # 绑定双击事件
            tree.bind('<Double-1>', lambda e, t=tree, y=year: self.on_receivable_double_click(e, t, y))
        
        # 更新账龄分析
        if hasattr(self, 'aging_labels'):
            for period, amount in aging_data.items():
                if period in self.aging_labels:
                    self.aging_labels[period].config(text=f'{amount:,.2f} 元')
    
    def on_receivable_double_click(self, event, tree, year):
        """应收账款列表双击事件"""
        region = tree.identify('region', event.x, event.y)
        if region != 'cell':
            return
        
        column = tree.identify_column(event.x)
        if column != '#13':  # 操作列
            return
        
        item = tree.selection()
        if not item:
            return
        
        values = tree.item(item[0])['values']
        contract_no = values[0]
        
        # 显示操作菜单
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="更新催款状态", command=lambda: self.update_collection_status_dialog(contract_no))
        menu.add_command(label="添加催款记录", command=lambda: self.add_collection_record_dialog(contract_no))
        menu.add_command(label="查看催款记录", command=lambda: self.view_collection_records(contract_no))
        menu.post(event.x_root, event.y_root)
    
    def update_collection_status_dialog(self, contract_no):
        """更新催款状态对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("更新催款状态")
        dialog.geometry("400x250")
        dialog.transient(self.root)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill='both', expand=True)
        
        ttk.Label(frame, text=f"合同编号: {contract_no}").grid(row=0, column=0, columnspan=2, pady=5)
        
        ttk.Label(frame, text="催款状态:").grid(row=1, column=0, sticky='e', pady=5)
        status_var = tk.StringVar(value='未催款')
        status_combo = ttk.Combobox(frame, textvariable=status_var, values=self.collection_status, state='readonly', width=25)
        status_combo.grid(row=1, column=1, pady=5)
        
        ttk.Label(frame, text="催款日期:").grid(row=2, column=0, sticky='e', pady=5)
        date_entry = DateEntry(frame, width=22, date_pattern='yyyy-mm-dd', locale='zh_CN')
        date_entry.grid(row=2, column=1, pady=5)
        
        ttk.Label(frame, text="备注:").grid(row=3, column=0, sticky='e', pady=5)
        note_entry = ttk.Entry(frame, width=28)
        note_entry.grid(row=3, column=1, pady=5)
        
        def save():
            self.db.update_collection_status(contract_no, status_var.get(), date_entry.get(), note_entry.get())
            messagebox.showinfo("成功", "催款状态更新成功")
            dialog.destroy()
            self.load_receivable_tabs()
        
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="保存", command=save).pack(side='left', padx=10)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side='left', padx=10)
    
    def add_collection_record_dialog(self, contract_no):
        """添加催款记录对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("添加催款记录")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill='both', expand=True)
        
        ttk.Label(frame, text=f"合同编号: {contract_no}").grid(row=0, column=0, columnspan=2, pady=5)
        
        ttk.Label(frame, text="催款日期:").grid(row=1, column=0, sticky='e', pady=5)
        date_entry = DateEntry(frame, width=22, date_pattern='yyyy-mm-dd', locale='zh_CN')
        date_entry.grid(row=1, column=1, pady=5)
        
        ttk.Label(frame, text="催款方式:").grid(row=2, column=0, sticky='e', pady=5)
        method_var = tk.StringVar()
        method_combo = ttk.Combobox(frame, textvariable=method_var, values=self.collection_methods, state='readonly', width=25)
        method_combo.grid(row=2, column=1, pady=5)
        
        ttk.Label(frame, text="联系人:").grid(row=3, column=0, sticky='e', pady=5)
        contact_entry = ttk.Entry(frame, width=28)
        contact_entry.grid(row=3, column=1, pady=5)
        
        ttk.Label(frame, text="催款内容:").grid(row=4, column=0, sticky='ne', pady=5)
        content_text = tk.Text(frame, width=30, height=3)
        content_text.grid(row=4, column=1, pady=5)
        
        ttk.Label(frame, text="对方反馈:").grid(row=5, column=0, sticky='ne', pady=5)
        feedback_text = tk.Text(frame, width=30, height=3)
        feedback_text.grid(row=5, column=1, pady=5)
        
        ttk.Label(frame, text="催款结果:").grid(row=6, column=0, sticky='e', pady=5)
        result_entry = ttk.Entry(frame, width=28)
        result_entry.grid(row=6, column=1, pady=5)
        
        def save():
            self.db.add_collection_record(
                contract_no, date_entry.get(), method_var.get(), contact_entry.get(),
                content_text.get('1.0', 'end-1c'), feedback_text.get('1.0', 'end-1c'), result_entry.get()
            )
            messagebox.showinfo("成功", "催款记录添加成功")
            dialog.destroy()
        
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="保存", command=save).pack(side='left', padx=10)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side='left', padx=10)
    
    def view_collection_records(self, contract_no):
        """查看催款记录"""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"催款记录 - {contract_no}")
        dialog.geometry("800x400")
        dialog.transient(self.root)
        
        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill='both', expand=True)
        
        columns = ('催款日期', '催款方式', '联系人', '催款内容', '对方反馈', '催款结果')
        tree = ttk.Treeview(frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120, anchor='center')
        
        tree.column('催款内容', width=200)
        tree.column('对方反馈', width=200)
        
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # 加载数据
        records = self.db.get_collection_records(contract_no)
        for record in records:
            tree.insert('', 'end', values=record)
    
    def create_yearly_tab(self, parent):
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        columns = ('年度', '合同数', '合同总额', '开票总额', '回款总额', '应收账款')
        self.yearly_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.yearly_tree.heading(col, text=col)
            self.yearly_tree.column(col, width=150, anchor='center')
        
        self.yearly_tree.pack(fill='both', expand=True)
        
        chart_frame = ttk.LabelFrame(parent, text="年度统计图表")
        chart_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.yearly_fig = Figure(figsize=(12, 4), dpi=100)
        self.yearly_canvas = FigureCanvasTkAgg(self.yearly_fig, master=chart_frame)
        self.yearly_canvas.get_tk_widget().pack(fill='both', expand=True)
    
    def create_region_tab(self, parent):
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(filter_frame, text="年度:").pack(side='left', padx=2)
        self.region_year_filter = ttk.Combobox(filter_frame, width=10, state='readonly')
        self.region_year_filter['values'] = ['全部'] + [str(y) for y in range(2030, 2019, -1)]
        self.region_year_filter.set('全部')
        self.region_year_filter.pack(side='left', padx=2)
        self.region_year_filter.bind('<<ComboboxSelected>>', lambda e: self.load_region_stats())
        
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        columns = ('区域', '年度', '合同内容', '合同数', '合同总额', '开票总额', '回款总额')
        self.region_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.region_tree.heading(col, text=col)
            self.region_tree.column(col, width=120, anchor='center')
        
        self.region_tree.pack(fill='both', expand=True)
        
        chart_frame = ttk.LabelFrame(parent, text="区域统计图表")
        chart_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.region_fig = Figure(figsize=(12, 4), dpi=100)
        self.region_canvas = FigureCanvasTkAgg(self.region_fig, master=chart_frame)
        self.region_canvas.get_tk_widget().pack(fill='both', expand=True)
    
    def create_salesperson_tab(self, parent):
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(filter_frame, text="年度:").pack(side='left', padx=2)
        self.sales_year_filter = ttk.Combobox(filter_frame, width=10, state='readonly')
        self.sales_year_filter['values'] = ['全部'] + [str(y) for y in range(2030, 2019, -1)]
        self.sales_year_filter.set('全部')
        self.sales_year_filter.pack(side='left', padx=2)
        self.sales_year_filter.bind('<<ComboboxSelected>>', lambda e: self.load_salesperson_stats())
        
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        columns = ('销售人员', '合同数', '合同总额', '开票总额', '回款总额', '应收账款')
        self.sales_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.sales_tree.heading(col, text=col)
            self.sales_tree.column(col, width=150, anchor='center')
        
        self.sales_tree.pack(fill='both', expand=True)
        
        chart_frame = ttk.LabelFrame(parent, text="销售人员业绩图表")
        chart_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.sales_fig = Figure(figsize=(12, 4), dpi=100)
        self.sales_canvas = FigureCanvasTkAgg(self.sales_fig, master=chart_frame)
        self.sales_canvas.get_tk_widget().pack(fill='both', expand=True)
    
    def update_salesperson_filter(self):
        """更新销售人员筛选器"""
        salespersons = ['全部'] + self.db.get_salespersons()
        self.salesperson_filter['values'] = salespersons
        self.salesperson_filter.set('全部')
    
    def sort_by_column(self, col):
        """按列排序"""
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False
        
        self.load_data()
    
    def clear_search(self):
        """清除搜索"""
        self.search_entry.delete(0, tk.END)
        self.year_filter.set('全部')
        self.region_filter.set('全部')
        self.salesperson_filter.set('全部')
        self.load_data()
    
    def load_data(self):
        year = None if self.year_filter.get() == '全部' else self.year_filter.get()
        region = None if self.region_filter.get() == '全部' else self.region_filter.get()
        salesperson = None if self.salesperson_filter.get() == '全部' else self.salesperson_filter.get()
        search_text = self.search_entry.get().strip() or None
        
        rows = self.db.get_contracts(year, region, salesperson, search_text)
        
        # 排序
        if self.sort_column:
            col_index = {
                '合同编号': 0, '项目代码': 1, '合同名称': 2, '对方单位': 3, '区域': 4,
                '销售人员': 5, '合同金额': 5, '签约日期': 6, '起始日期': 7, '终止日期': 8,
                '合同内容': 9, '累计开票': 11, '累计回款': 12, '应收账款': None
            }
            
            if self.sort_column in col_index:
                idx = col_index[self.sort_column]
                if idx is not None:
                    if self.sort_column in ['合同金额', '累计开票', '累计回款']:
                        rows = sorted(rows, key=lambda x: x[idx] or 0, reverse=self.sort_reverse)
                    else:
                        rows = sorted(rows, key=lambda x: str(x[idx] or ''), reverse=self.sort_reverse)
        
        for item in self.contract_tree.get_children():
            self.contract_tree.delete(item)
        
        for row in rows:
            contract_no, project_code, contract_name, company, region, amount, \
            sign_date, start_date, end_date, content, salesperson, collection_status, collection_date, \
            invoice, payment = row
            receivable = invoice - payment
            self.contract_tree.insert('', 'end', values=(
                contract_no, project_code, contract_name or '', company, region, salesperson or '',
                f'{amount:,.2f}' if amount else '0.00',
                sign_date or '', start_date or '', end_date or '', content or '',
                f'{invoice:,.2f}', f'{payment:,.2f}', f'{receivable:,.2f}'
            ))
        
        self.load_yearly_stats()
        self.load_region_stats()
        self.load_salesperson_stats()
    
    def load_warning_data(self):
        """加载到期预警数据"""
        for item in self.warning_tree.get_children():
            self.warning_tree.delete(item)
        
        today = datetime.now()
        
        # 获取即将到期的合同（30天内）
        expiring = self.db.get_expiring_contracts(30)
        
        # 获取已到期的合同
        expired = self.db.get_expired_contracts()
        
        # 合并数据
        all_contracts = []
        
        for row in expiring:
            end_date = row[8]
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                days_left = (end_dt - today).days
            except:
                days_left = 0
            all_contracts.append((row, days_left, 'expiring'))
        
        for row in expired:
            end_date = row[8]
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                days_left = (end_dt - today).days
            except:
                days_left = -999
            all_contracts.append((row, days_left, 'expired'))
        
        # 按剩余天数排序
        all_contracts.sort(key=lambda x: x[1])
        
        for row, days_left, status in all_contracts:
            contract_no, project_code, contract_name, company, region, amount, \
            sign_date, start_date, end_date, content, salesperson, \
            invoice, payment = row
            receivable = invoice - payment
            
            # 确定预警等级
            if days_left >= 0:
                tag = 'warning_yellow'
            elif days_left >= -30:
                tag = 'warning_orange'
            else:
                tag = 'warning_red'
            
            self.warning_tree.insert('', 'end', values=(
                contract_no, contract_name or '', company, region, salesperson or '',
                f'{amount:,.2f}' if amount else '0.00',
                end_date or '', days_left,
                f'{invoice:,.2f}', f'{payment:,.2f}', f'{receivable:,.2f}'
            ), tags=(tag,))
    
    def check_expiring_contracts(self):
        """检查即将到期的合同并弹出提醒"""
        expiring = self.db.get_expiring_contracts(30)
        
        if expiring:
            count = len(expiring)
            message = f"当前有 {count} 份合同将在30天内到期！\n\n"
            message += "即将到期的合同：\n"
            
            for i, row in enumerate(expiring[:5]):  # 只显示前5个
                contract_no = row[0]
                contract_name = row[2] or ''
                end_date = row[8] or ''
                message += f"{i+1}. {contract_no} - {contract_name} (到期: {end_date})\n"
            
            if count > 5:
                message += f"\n... 还有 {count - 5} 份合同即将到期"
            
            messagebox.showwarning("到期预警", message)
    
    def load_yearly_stats(self):
        rows = self.db.get_yearly_stats()
        
        for item in self.yearly_tree.get_children():
            self.yearly_tree.delete(item)
        
        for row in rows:
            year, count, total, invoice, payment = row
            receivable = invoice - payment
            self.yearly_tree.insert('', 'end', values=(
                year, count,
                f'{total:,.2f}' if total else '0.00',
                f'{invoice:,.2f}' if invoice else '0.00',
                f'{payment:,.2f}' if payment else '0.00',
                f'{receivable:,.2f}'
            ))
        
        self.draw_yearly_chart(rows)
    
    def draw_yearly_chart(self, rows):
        self.yearly_fig.clear()
        
        if not rows:
            self.yearly_canvas.draw()
            return
        
        years = [row[0] for row in rows][::-1]
        invoices = [row[3] or 0 for row in rows][::-1]
        payments = [row[4] or 0 for row in rows][::-1]
        
        ax = self.yearly_fig.add_subplot(111)
        
        x = range(len(years))
        width = 0.35
        
        bars1 = ax.bar([i - width/2 for i in x], invoices, width, label='开票总额', color='#3498db')
        bars2 = ax.bar([i + width/2 for i in x], payments, width, label='回款总额', color='#2ecc71')
        
        ax.set_xlabel('年度')
        ax.set_ylabel('金额（元）')
        ax.set_title('年度开票与回款统计')
        ax.set_xticks(x)
        ax.set_xticklabels(years)
        ax.legend()
        
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height/10000:.1f}万',
                           ha='center', va='bottom', fontsize=8)
        
        self.yearly_fig.tight_layout()
        self.yearly_canvas.draw()
    
    def load_region_stats(self):
        year = None if self.region_year_filter.get() == '全部' else self.region_year_filter.get()
        rows = self.db.get_region_stats(year)
        
        for item in self.region_tree.get_children():
            self.region_tree.delete(item)
        
        for row in rows:
            region, year, content, count, total, invoice, payment = row
            self.region_tree.insert('', 'end', values=(
                region, year, content or '', count,
                f'{total:,.2f}' if total else '0.00',
                f'{invoice:,.2f}' if invoice else '0.00',
                f'{payment:,.2f}' if payment else '0.00'
            ))
        
        self.draw_region_chart(rows)
    
    def draw_region_chart(self, rows):
        self.region_fig.clear()
        
        if not rows:
            self.region_canvas.draw()
            return
        
        region_data = {}
        for row in rows:
            region = row[0]
            if region not in region_data:
                region_data[region] = {'total': 0, 'invoice': 0, 'payment': 0}
            region_data[region]['total'] += row[4] or 0
            region_data[region]['invoice'] += row[5] or 0
            region_data[region]['payment'] += row[6] or 0
        
        regions = list(region_data.keys())
        totals = [region_data[r]['total'] for r in regions]
        invoices = [region_data[r]['invoice'] for r in regions]
        payments = [region_data[r]['payment'] for r in regions]
        
        ax = self.region_fig.add_subplot(111)
        
        x = range(len(regions))
        width = 0.25
        
        bars1 = ax.bar([i - width for i in x], totals, width, label='合同总额', color='#e74c3c')
        bars2 = ax.bar([i for i in x], invoices, width, label='开票总额', color='#3498db')
        bars3 = ax.bar([i + width for i in x], payments, width, label='回款总额', color='#2ecc71')
        
        ax.set_xlabel('区域')
        ax.set_ylabel('金额（元）')
        ax.set_title('区域合同统计')
        ax.set_xticks(x)
        ax.set_xticklabels(regions, rotation=45, ha='right')
        ax.legend()
        
        self.region_fig.tight_layout()
        self.region_canvas.draw()
    
    def load_salesperson_stats(self):
        year = None if self.sales_year_filter.get() == '全部' else self.sales_year_filter.get()
        rows = self.db.get_salesperson_stats(year)
        
        for item in self.sales_tree.get_children():
            self.sales_tree.delete(item)
        
        for row in rows:
            salesperson, count, total, invoice, payment = row
            receivable = invoice - payment
            self.sales_tree.insert('', 'end', values=(
                salesperson or '未指定', count,
                f'{total:,.2f}' if total else '0.00',
                f'{invoice:,.2f}' if invoice else '0.00',
                f'{payment:,.2f}' if payment else '0.00',
                f'{receivable:,.2f}'
            ))
        
        self.draw_salesperson_chart(rows)
    
    def draw_salesperson_chart(self, rows):
        self.sales_fig.clear()
        
        if not rows:
            self.sales_canvas.draw()
            return
        
        salespersons = [row[0] or '未指定' for row in rows]
        totals = [row[2] or 0 for row in rows]
        
        ax = self.sales_fig.add_subplot(111)
        
        x = range(len(salespersons))
        bars = ax.bar(x, totals, color='#9b59b6')
        
        ax.set_xlabel('销售人员')
        ax.set_ylabel('合同总额（元）')
        ax.set_title('销售人员业绩统计')
        ax.set_xticks(x)
        ax.set_xticklabels(salespersons, rotation=45, ha='right')
        
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height/10000:.1f}万',
                       ha='center', va='bottom', fontsize=8)
        
        self.sales_fig.tight_layout()
        self.sales_canvas.draw()
    
    def add_contract(self):
        self.show_contract_dialog()
    
    def edit_contract(self):
        selected = self.contract_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个合同")
            return
        
        contract_no = self.contract_tree.item(selected[0])['values'][0]
        self.show_contract_dialog(contract_no)
    
    def delete_contract(self):
        selected = self.contract_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个合同")
            return
        
        contract_no = self.contract_tree.item(selected[0])['values'][0]
        contract_name = self.contract_tree.item(selected[0])['values'][2]
        
        if not messagebox.askyesno("确认删除", 
                                   f"确定要删除合同 '{contract_no}' 吗？\n\n合同名称: {contract_name}\n\n注意：该合同的所有开票和回款记录也将被删除！"):
            return
        
        if self.db.delete_contract(contract_no):
            messagebox.showinfo("成功", "合同删除成功")
            self.load_data()
        else:
            messagebox.showerror("错误", "合同删除失败")
    
    def show_contract_dialog(self, contract_no=None):
        dialog = tk.Toplevel(self.root)
        dialog.title("修改合同" if contract_no else "添加合同")
        dialog.geometry("600x650")
        dialog.transient(self.root)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill='both', expand=True)
        
        fields = {}
        row = 0
        
        # 合同编号
        ttk.Label(frame, text="合同编号:").grid(row=row, column=0, sticky='e', pady=5)
        fields['合同编号'] = ttk.Entry(frame, width=30)
        fields['合同编号'].grid(row=row, column=1, pady=5)
        row += 1
        
        # 项目代码
        ttk.Label(frame, text="项目代码:").grid(row=row, column=0, sticky='e', pady=5)
        fields['项目代码'] = ttk.Entry(frame, width=30)
        fields['项目代码'].grid(row=row, column=1, pady=5)
        row += 1
        
        # 合同名称
        ttk.Label(frame, text="合同名称:").grid(row=row, column=0, sticky='e', pady=5)
        fields['合同名称'] = ttk.Entry(frame, width=30)
        fields['合同名称'].grid(row=row, column=1, pady=5)
        row += 1
        
        # 对方单位
        ttk.Label(frame, text="对方单位:").grid(row=row, column=0, sticky='e', pady=5)
        fields['对方单位'] = ttk.Entry(frame, width=30)
        fields['对方单位'].grid(row=row, column=1, pady=5)
        row += 1
        
        # 区域
        ttk.Label(frame, text="区域:").grid(row=row, column=0, sticky='e', pady=5)
        fields['区域'] = ttk.Combobox(frame, width=27, values=self.regions, state='readonly')
        fields['区域'].grid(row=row, column=1, pady=5)
        row += 1
        
        # 销售人员
        ttk.Label(frame, text="销售人员:").grid(row=row, column=0, sticky='e', pady=5)
        salesperson_frame = ttk.Frame(frame)
        salesperson_frame.grid(row=row, column=1, pady=5, sticky='w')
        
        salespersons = self.db.get_salespersons()
        fields['销售人员'] = ttk.Combobox(salesperson_frame, width=22, values=salespersons)
        fields['销售人员'].pack(side='left')
        
        def add_new_salesperson():
            new_name = fields['销售人员'].get().strip()
            if new_name and new_name not in salespersons:
                if self.db.add_salesperson(new_name):
                    salespersons.append(new_name)
                    fields['销售人员']['values'] = salespersons
                    messagebox.showinfo("成功", f"销售人员 '{new_name}' 已添加")
                    self.update_salesperson_filter()
        
        ttk.Button(salesperson_frame, text="+", width=3, command=add_new_salesperson).pack(side='left', padx=5)
        row += 1
        
        # 合同金额
        ttk.Label(frame, text="合同金额:").grid(row=row, column=0, sticky='e', pady=5)
        fields['合同金额'] = ttk.Entry(frame, width=30)
        fields['合同金额'].grid(row=row, column=1, pady=5)
        row += 1
        
        # 实际签约日期
        ttk.Label(frame, text="实际签约日期:").grid(row=row, column=0, sticky='e', pady=5)
        fields['实际签约日期'] = DateEntry(frame, width=27, date_pattern='yyyy-mm-dd', locale='zh_CN')
        fields['实际签约日期'].grid(row=row, column=1, pady=5)
        ttk.Label(frame, text="（用于确定合同年度）", foreground='gray').grid(row=row, column=2, sticky='w', pady=5)
        row += 1
        
        # 起始日期
        ttk.Label(frame, text="起始日期:").grid(row=row, column=0, sticky='e', pady=5)
        fields['起始日期'] = DateEntry(frame, width=27, date_pattern='yyyy-mm-dd', locale='zh_CN')
        fields['起始日期'].grid(row=row, column=1, pady=5)
        row += 1
        
        # 终止日期
        ttk.Label(frame, text="终止日期:").grid(row=row, column=0, sticky='e', pady=5)
        fields['终止日期'] = DateEntry(frame, width=27, date_pattern='yyyy-mm-dd', locale='zh_CN')
        fields['终止日期'].grid(row=row, column=1, pady=5)
        row += 1
        
        # 合同内容
        ttk.Label(frame, text="合同内容:").grid(row=row, column=0, sticky='e', pady=5)
        fields['合同内容'] = ttk.Combobox(frame, width=27, values=self.contract_types, state='readonly')
        fields['合同内容'].grid(row=row, column=1, pady=5)
        row += 1
        
        # 如果是修改，填充现有数据
        if contract_no:
            contract = self.db.get_contract_by_no(contract_no)
            if contract:
                fields['合同编号'].insert(0, contract[1] or '')
                fields['合同编号'].config(state='disabled')
                fields['项目代码'].insert(0, contract[2] or '')
                fields['合同名称'].insert(0, contract[3] or '')
                fields['对方单位'].insert(0, contract[4] or '')
                fields['区域'].set(contract[5] or '')
                fields['销售人员'].set(contract[11] or '')
                fields['合同金额'].insert(0, str(contract[6] or ''))
                
                if contract[7]:
                    try:
                        fields['实际签约日期'].set_date(contract[7])
                    except:
                        pass
                if contract[8]:
                    try:
                        fields['起始日期'].set_date(contract[8])
                    except:
                        pass
                if contract[9]:
                    try:
                        fields['终止日期'].set_date(contract[9])
                    except:
                        pass
                
                fields['合同内容'].set(contract[10] or '')
        
        # 按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=20)
        
        def save():
            try:
                contract_no_val = fields['合同编号'].get().strip()
                project_code_val = fields['项目代码'].get().strip()
                contract_name_val = fields['合同名称'].get().strip()
                company_val = fields['对方单位'].get().strip()
                region_val = fields['区域'].get()
                salesperson_val = fields['销售人员'].get().strip()
                amount_val = fields['合同金额'].get().strip()
                sign_date_val = fields['实际签约日期'].get()
                start_date_val = fields['起始日期'].get()
                end_date_val = fields['终止日期'].get()
                content_val = fields['合同内容'].get()
                
                if not contract_no_val:
                    messagebox.showwarning("警告", "合同编号不能为空")
                    return
                
                try:
                    amount = float(amount_val or 0)
                except ValueError:
                    messagebox.showwarning("警告", "合同金额必须是数字")
                    return
                
                data = {
                    '合同编号': contract_no_val,
                    '项目代码': project_code_val,
                    '合同名称': contract_name_val,
                    '对方单位名称': company_val,
                    '区域': region_val,
                    '销售人员': salesperson_val,
                    '合同金额': amount,
                    '实际签约日期': sign_date_val,
                    '合同起始日期': start_date_val,
                    '合同终止日期': end_date_val,
                    '合同内容': content_val
                }
                
                if contract_no:
                    if self.db.update_contract(contract_no, data):
                        messagebox.showinfo("成功", "合同修改成功")
                        dialog.destroy()
                        self.load_data()
                    else:
                        messagebox.showerror("错误", "合同修改失败")
                else:
                    if self.db.add_contract(data):
                        messagebox.showinfo("成功", "合同添加成功")
                        dialog.destroy()
                        self.load_data()
                    else:
                        messagebox.showwarning("警告", "合同编号已存在")
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {str(e)}")
        
        ttk.Button(btn_frame, text="保存", command=save).pack(side='left', padx=10)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side='left', padx=10)
    
    def add_invoice(self):
        selected = self.contract_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个合同")
            return
        
        contract_no = self.contract_tree.item(selected[0])['values'][0]
        
        dialog = tk.Toplevel(self.root)
        dialog.title("添加开票记录")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill='both', expand=True)
        
        ttk.Label(frame, text="合同编号:").grid(row=0, column=0, sticky='e', pady=5)
        ttk.Label(frame, text=contract_no).grid(row=0, column=1, sticky='w', pady=5)
        
        ttk.Label(frame, text="开票日期:").grid(row=1, column=0, sticky='e', pady=5)
        date_entry = DateEntry(frame, width=22, date_pattern='yyyy-mm-dd', locale='zh_CN')
        date_entry.grid(row=1, column=1, pady=5)
        
        ttk.Label(frame, text="开票金额:").grid(row=2, column=0, sticky='e', pady=5)
        amount_entry = ttk.Entry(frame, width=25)
        amount_entry.grid(row=2, column=1, pady=5)
        
        def save():
            try:
                amount = float(amount_entry.get().strip())
                date = date_entry.get()
                self.db.add_invoice(contract_no, date, amount)
                messagebox.showinfo("成功", "开票记录添加成功")
                dialog.destroy()
                self.load_data()
            except ValueError:
                messagebox.showwarning("警告", "金额必须是数字")
        
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="保存", command=save).pack(side='left', padx=10)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side='left', padx=10)
    
    def add_payment(self):
        selected = self.contract_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个合同")
            return
        
        contract_no = self.contract_tree.item(selected[0])['values'][0]
        
        dialog = tk.Toplevel(self.root)
        dialog.title("添加回款记录")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill='both', expand=True)
        
        ttk.Label(frame, text="合同编号:").grid(row=0, column=0, sticky='e', pady=5)
        ttk.Label(frame, text=contract_no).grid(row=0, column=1, sticky='w', pady=5)
        
        ttk.Label(frame, text="回款日期:").grid(row=1, column=0, sticky='e', pady=5)
        date_entry = DateEntry(frame, width=22, date_pattern='yyyy-mm-dd', locale='zh_CN')
        date_entry.grid(row=1, column=1, pady=5)
        
        ttk.Label(frame, text="回款金额:").grid(row=2, column=0, sticky='e', pady=5)
        amount_entry = ttk.Entry(frame, width=25)
        amount_entry.grid(row=2, column=1, pady=5)
        
        def save():
            try:
                amount = float(amount_entry.get().strip())
                date = date_entry.get()
                self.db.add_payment(contract_no, date, amount)
                messagebox.showinfo("成功", "回款记录添加成功")
                dialog.destroy()
                self.load_data()
            except ValueError:
                messagebox.showwarning("警告", "金额必须是数字")
        
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="保存", command=save).pack(side='left', padx=10)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side='left', padx=10)
    
    def import_data(self):
        file_path = filedialog.askopenfilename(
            title="选择数据文件",
            filetypes=[
                ("Excel文件", "*.xlsx *.xls"),
                ("CSV文件", "*.csv"),
                ("所有文件", "*.*")
            ]
        )
        
        if not file_path:
            return
        
        try:
            count = self.db.import_from_file(file_path)
            messagebox.showinfo("成功", f"成功导入 {count} 条合同记录")
            self.load_data()
            self.update_salesperson_filter()
        except Exception as e:
            messagebox.showerror("错误", f"导入失败: {str(e)}")
    
    def backup_database(self):
        """备份数据库"""
        file_path = filedialog.asksaveasfilename(
            title="保存备份文件",
            defaultextension=".db",
            filetypes=[("数据库文件", "*.db"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            import shutil
            shutil.copy2(DB_PATH, file_path)
            messagebox.showinfo("成功", f"数据库已备份到:\n{file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"备份失败: {str(e)}")
    
    def restore_database(self):
        """恢复数据库"""
        if not messagebox.askyesno("确认", "恢复数据库将覆盖当前数据，是否继续？"):
            return
        
        file_path = filedialog.askopenfilename(
            title="选择备份文件",
            filetypes=[("数据库文件", "*.db"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            import shutil
            shutil.copy2(file_path, DB_PATH)
            messagebox.showinfo("成功", "数据库已恢复，程序将重新启动")
            self.root.destroy()
        except Exception as e:
            messagebox.showerror("错误", f"恢复失败: {str(e)}")
    
    def export_to_excel(self):
        """导出到Excel"""
        file_path = filedialog.asksaveasfilename(
            title="保存Excel文件",
            defaultextension=".xlsx",
            filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "合同列表"
            
            # 写入表头
            headers = ['合同编号', '项目代码', '合同名称', '对方单位', '区域', '销售人员',
                      '合同金额', '签约日期', '起始日期', '终止日期', '合同内容',
                      '累计开票', '累计回款', '应收账款']
            ws.append(headers)
            
            # 写入数据
            for item in self.contract_tree.get_children():
                values = self.contract_tree.item(item)['values']
                ws.append(values)
            
            wb.save(file_path)
            messagebox.showinfo("成功", f"数据已导出到:\n{file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {str(e)}")
    
    def export_warning_list(self):
        """导出预警列表"""
        file_path = filedialog.asksaveasfilename(
            title="保存预警列表",
            defaultextension=".xlsx",
            filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "到期预警"
            
            headers = ['合同编号', '合同名称', '对方单位', '区域', '销售人员',
                      '合同金额', '终止日期', '剩余天数', '累计开票', '累计回款', '应收账款']
            ws.append(headers)
            
            for item in self.warning_tree.get_children():
                values = self.warning_tree.item(item)['values']
                ws.append(values)
            
            wb.save(file_path)
            messagebox.showinfo("成功", f"预警列表已导出到:\n{file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {str(e)}")
    
    def export_receivable_excel(self, year):
        """导出应收账款"""
        file_path = filedialog.asksaveasfilename(
            title="保存应收账款",
            defaultextension=".xlsx",
            filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = f"{year}年应收账款"
            
            headers = ['合同编号', '合同名称', '对方单位', '区域', '销售人员',
                      '合同金额', '签约日期', '账龄(天)', '累计开票', '累计回款',
                      '应收金额', '催款状态']
            ws.append(headers)
            
            if year in self.receivable_trees:
                tree = self.receivable_trees[year]
                for item in tree.get_children():
                    values = tree.item(item)['values'][:12]  # 不包含操作列
                    ws.append(values)
            
            wb.save(file_path)
            messagebox.showinfo("成功", f"应收账款已导出到:\n{file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {str(e)}")
    
    def show_about(self):
        """显示关于对话框"""
        messagebox.showinfo("关于", 
            "合同管理系统 v4.0\n\n"
            "功能：\n"
            "- 合同录入、修改、删除\n"
            "- 开票回款管理\n"
            "- 销售人员管理\n"
            "- 搜索和排序\n"
            "- 到期合同预警\n"
            "- 应收账款催款\n"
            "- 统计分析\n\n"
            "数据存储位置：\n"
            f"{DATA_DIR}")


def main():
    root = tk.Tk()
    app = ContractManagerApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
