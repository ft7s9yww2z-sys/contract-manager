#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合同管理系统 - 轻量版 v3.2
功能：合同录入、开票回款、统计分析、图表展示、日期选择器、删除合同
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import DateEntry
import sqlite3
import os
import sys
from datetime import datetime
import csv
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
    # Windows: 使用 AppData/Local 目录
    DATA_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'ContractManager')
else:
    # macOS/Linux: 使用用户主目录
    DATA_DIR = os.path.join(os.path.expanduser('~'), '.contract_manager')

# 确保数据目录存在
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
                    创建时间 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        else:
            if '合同名称' not in columns:
                cursor.execute('ALTER TABLE contracts ADD COLUMN 合同名称 TEXT')
            if '实际签约日期' not in columns:
                cursor.execute('ALTER TABLE contracts ADD COLUMN 实际签约日期 TEXT')
        
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
        
        conn.commit()
        conn.close()
    
    def add_contract(self, data):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO contracts 
                (合同编号, 项目代码, 合同名称, 对方单位名称, 区域, 合同金额, 
                 实际签约日期, 合同起始日期, 合同终止日期, 合同内容)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (data['合同编号'], data['项目代码'], data['合同名称'],
                  data['对方单位名称'], data['区域'], data['合同金额'],
                  data['实际签约日期'], data['合同起始日期'], 
                  data['合同终止日期'], data['合同内容']))
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
                实际签约日期=?, 合同起始日期=?, 合同终止日期=?, 合同内容=?
                WHERE 合同编号=?
            ''', (data['项目代码'], data['合同名称'], data['对方单位名称'],
                  data['区域'], data['合同金额'], data['实际签约日期'],
                  data['合同起始日期'], data['合同终止日期'], 
                  data['合同内容'], contract_no))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def get_contract_by_no(self, contract_no):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM contracts WHERE 合同编号=?', (contract_no,))
        row = cursor.fetchone()
        conn.close()
        return row
    
    def delete_contract(self, contract_no):
        """删除合同及其相关的开票和回款记录"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # 先删除相关的开票记录
            cursor.execute('DELETE FROM invoices WHERE 合同编号=?', (contract_no,))
            # 删除相关的回款记录
            cursor.execute('DELETE FROM payments WHERE 合同编号=?', (contract_no,))
            # 删除合同
            cursor.execute('DELETE FROM contracts WHERE 合同编号=?', (contract_no,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def get_contracts(self, year=None, region=None):
        conn = self.get_connection()
        query = '''
            SELECT 
                c.合同编号, c.项目代码, c.合同名称, c.对方单位名称, c.区域, c.合同金额,
                c.实际签约日期, c.合同起始日期, c.合同终止日期, c.合同内容,
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
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " GROUP BY c.合同编号 ORDER BY c.创建时间 DESC"
        
        cursor = conn.cursor()
        cursor.execute(query, params)
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
    
    def import_from_file(self, file_path):
        """从CSV或Excel导入"""
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
                                '合同内容': str(row_data.get('合同内容', '') or row_data.get('合同内容（发生项目）', '') or '')
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
                            '合同内容': row.get('合同内容', '')
                        }
                        if data['合同编号'] and self.add_contract(data):
                            count += 1
            
            return count
        except Exception as e:
            raise e
    
    def _format_date(self, date_value):
        """格式化日期"""
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
        self.root.title("合同管理系统 v3.2")
        self.root.geometry("1400x800")
        
        self.db = DatabaseManager()
        
        self.regions = ['北方区', '西北区', '华东区', '华南区', '国际部', '其他']
        self.contract_types = ['维保费', '维修费', '技术服务费', '其他']
        
        self.create_widgets()
        self.load_data()
    
    def create_widgets(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        contract_frame = ttk.Frame(notebook)
        notebook.add(contract_frame, text='合同管理')
        self.create_contract_tab(contract_frame)
        
        yearly_frame = ttk.Frame(notebook)
        notebook.add(yearly_frame, text='年度统计')
        self.create_yearly_tab(yearly_frame)
        
        region_frame = ttk.Frame(notebook)
        notebook.add(region_frame, text='区域统计')
        self.create_region_tab(region_frame)
    
    def create_contract_tab(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(toolbar, text="添加合同", command=self.add_contract).pack(side='left', padx=2)
        ttk.Button(toolbar, text="修改合同", command=self.edit_contract).pack(side='left', padx=2)
        ttk.Button(toolbar, text="删除合同", command=self.delete_contract).pack(side='left', padx=2)
        ttk.Button(toolbar, text="添加开票", command=self.add_invoice).pack(side='left', padx=2)
        ttk.Button(toolbar, text="添加回款", command=self.add_payment).pack(side='left', padx=2)
        ttk.Button(toolbar, text="导入数据", command=self.import_data).pack(side='left', padx=2)
        ttk.Button(toolbar, text="刷新", command=self.load_data).pack(side='left', padx=2)
        
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(filter_frame, text="年度:").pack(side='left', padx=2)
        self.year_filter = ttk.Combobox(filter_frame, width=10, state='readonly')
        self.year_filter['values'] = ['全部'] + [str(y) for y in range(2026, 2019, -1)]
        self.year_filter.set('全部')
        self.year_filter.pack(side='left', padx=2)
        self.year_filter.bind('<<ComboboxSelected>>', lambda e: self.load_data())
        
        ttk.Label(filter_frame, text="区域:").pack(side='left', padx=2)
        self.region_filter = ttk.Combobox(filter_frame, width=12, state='readonly')
        self.region_filter['values'] = ['全部'] + self.regions
        self.region_filter.set('全部')
        self.region_filter.pack(side='left', padx=2)
        self.region_filter.bind('<<ComboboxSelected>>', lambda e: self.load_data())
        
        columns = ('合同编号', '项目代码', '合同名称', '对方单位', '区域', '合同金额', 
                  '签约日期', '起始日期', '终止日期', '合同内容', '累计开票', '累计回款', '应收账款')
        self.contract_tree = ttk.Treeview(parent, columns=columns, show='headings', height=25)
        
        for col in columns:
            self.contract_tree.heading(col, text=col)
            self.contract_tree.column(col, width=100, anchor='center')
        
        self.contract_tree.column('合同名称', width=150)
        self.contract_tree.column('对方单位', width=150)
        self.contract_tree.column('合同金额', width=120)
        self.contract_tree.column('签约日期', width=100)
        self.contract_tree.column('累计开票', width=120)
        self.contract_tree.column('累计回款', width=120)
        self.contract_tree.column('应收账款', width=120)
        
        scrollbar = ttk.Scrollbar(parent, orient='vertical', command=self.contract_tree.yview)
        self.contract_tree.configure(yscrollcommand=scrollbar.set)
        
        self.contract_tree.pack(side='left', fill='both', expand=True, padx=5)
        scrollbar.pack(side='right', fill='y', pady=5)
    
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
        self.region_year_filter['values'] = ['全部'] + [str(y) for y in range(2026, 2019, -1)]
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
    
    def load_data(self):
        year = None if self.year_filter.get() == '全部' else self.year_filter.get()
        region = None if self.region_filter.get() == '全部' else self.region_filter.get()
        
        rows = self.db.get_contracts(year, region)
        
        for item in self.contract_tree.get_children():
            self.contract_tree.delete(item)
        
        for row in rows:
            contract_no, project_code, contract_name, company, region, amount, \
            sign_date, start_date, end_date, content, invoice, payment = row
            receivable = invoice - payment
            self.contract_tree.insert('', 'end', values=(
                contract_no, project_code, contract_name or '', company, region, 
                f'{amount:,.2f}' if amount else '0.00',
                sign_date or '', start_date or '', end_date or '', content or '',
                f'{invoice:,.2f}', f'{payment:,.2f}', f'{receivable:,.2f}'
            ))
        
        self.load_yearly_stats()
        self.load_region_stats()
    
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
        """删除选中的合同"""
        selected = self.contract_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个合同")
            return
        
        contract_no = self.contract_tree.item(selected[0])['values'][0]
        contract_name = self.contract_tree.item(selected[0])['values'][2]
        
        # 确认删除
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
        dialog.geometry("600x600")
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
        
        # 合同金额
        ttk.Label(frame, text="合同金额:").grid(row=row, column=0, sticky='e', pady=5)
        fields['合同金额'] = ttk.Entry(frame, width=30)
        fields['合同金额'].grid(row=row, column=1, pady=5)
        row += 1
        
        # 实际签约日期 - 使用日期选择器
        ttk.Label(frame, text="实际签约日期:").grid(row=row, column=0, sticky='e', pady=5)
        fields['实际签约日期'] = DateEntry(frame, width=27, date_pattern='yyyy-mm-dd', locale='zh_CN')
        fields['实际签约日期'].grid(row=row, column=1, pady=5)
        ttk.Label(frame, text="（用于确定合同年度）", foreground='gray').grid(row=row, column=2, sticky='w', pady=5)
        row += 1
        
        # 起始日期 - 使用日期选择器
        ttk.Label(frame, text="起始日期:").grid(row=row, column=0, sticky='e', pady=5)
        fields['起始日期'] = DateEntry(frame, width=27, date_pattern='yyyy-mm-dd', locale='zh_CN')
        fields['起始日期'].grid(row=row, column=1, pady=5)
        row += 1
        
        # 终止日期 - 使用日期选择器
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
                fields['合同金额'].insert(0, str(contract[6] or ''))
                
                # 设置日期选择器的值
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
                # 获取表单数据
                contract_no_val = fields['合同编号'].get().strip()
                project_code_val = fields['项目代码'].get().strip()
                contract_name_val = fields['合同名称'].get().strip()
                company_val = fields['对方单位'].get().strip()
                region_val = fields['区域'].get()
                amount_val = fields['合同金额'].get().strip()
                sign_date_val = fields['实际签约日期'].get()
                start_date_val = fields['起始日期'].get()
                end_date_val = fields['终止日期'].get()
                content_val = fields['合同内容'].get()
                
                # 验证必填字段
                if not contract_no_val:
                    messagebox.showwarning("警告", "合同编号不能为空")
                    return
                
                # 验证金额
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
                    '合同金额': amount,
                    '实际签约日期': sign_date_val,
                    '合同起始日期': start_date_val,
                    '合同终止日期': end_date_val,
                    '合同内容': content_val
                }
                
                if contract_no:
                    # 修改
                    if self.db.update_contract(contract_no, data):
                        messagebox.showinfo("成功", "合同修改成功")
                        dialog.destroy()
                        self.load_data()
                    else:
                        messagebox.showerror("错误", "合同修改失败")
                else:
                    # 添加
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
        except Exception as e:
            messagebox.showerror("错误", f"导入失败: {str(e)}")


def main():
    root = tk.Tk()
    app = ContractManagerApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
