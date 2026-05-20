#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合同管理系统 - 轻量版
使用 tkinter 开发，打包后体积更小
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
from datetime import datetime
import csv

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'contracts.db')


class DatabaseManager:
    """数据库管理"""
    
    def __init__(self):
        self.init_database()
    
    def get_connection(self):
        return sqlite3.connect(DB_PATH)
    
    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 合同表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                合同编号 TEXT UNIQUE NOT NULL,
                项目代码 TEXT,
                对方单位名称 TEXT,
                区域 TEXT,
                合同金额 REAL,
                合同起始日期 TEXT,
                合同终止日期 TEXT,
                合同内容 TEXT,
                创建时间 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 开票表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                合同编号 TEXT NOT NULL,
                开票日期 TEXT,
                开票金额 REAL,
                FOREIGN KEY (合同编号) REFERENCES contracts(合同编号)
            )
        ''')
        
        # 回款表
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
                (合同编号, 项目代码, 对方单位名称, 区域, 合同金额, 合同起始日期, 合同终止日期, 合同内容)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (data['合同编号'], data['项目代码'], data['对方单位名称'], 
                  data['区域'], data['合同金额'], data['合同起始日期'], 
                  data['合同终止日期'], data['合同内容']))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def get_contracts(self, year=None, region=None):
        conn = self.get_connection()
        query = '''
            SELECT 
                c.合同编号, c.项目代码, c.对方单位名称, c.区域, c.合同金额,
                c.合同起始日期, c.合同终止日期, c.合同内容,
                COALESCE(SUM(i.开票金额), 0) as 累计开票,
                COALESCE(SUM(p.回款金额), 0) as 累计回款
            FROM contracts c
            LEFT JOIN invoices i ON c.合同编号 = i.合同编号
            LEFT JOIN payments p ON c.合同编号 = p.合同编号
        '''
        
        conditions = []
        params = []
        
        if year:
            conditions.append("strftime('%Y', c.合同起始日期) = ?")
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
                strftime('%Y', c.合同起始日期) as 年度,
                COUNT(c.合同编号) as 合同数,
                SUM(c.合同金额) as 合同总额,
                COALESCE(SUM(i.开票金额), 0) as 开票总额,
                COALESCE(SUM(p.回款金额), 0) as 回款总额
            FROM contracts c
            LEFT JOIN invoices i ON c.合同编号 = i.合同编号
            LEFT JOIN payments p ON c.合同编号 = p.合同编号
            GROUP BY strftime('%Y', c.合同起始日期)
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
                strftime('%Y', c.合同起始日期) as 年度,
                c.合同内容,
                COUNT(c.合同编号) as 合同数,
                SUM(c.合同金额) as 合同总额,
                COALESCE(SUM(i.开票金额), 0) as 开票总额,
                COALESCE(SUM(p.回款金额), 0) as 回款总额
            FROM contracts c
            LEFT JOIN invoices i ON c.合同编号 = i.合同编号
            LEFT JOIN payments p ON c.合同编号 = p.合同编号
        '''
        
        params = []
        if year:
            query += " WHERE strftime('%Y', c.合同起始日期) = ?"
            params.append(str(year))
        
        query += " GROUP BY c.区域, strftime('%Y', c.合同起始日期), c.合同内容 ORDER BY 年度 DESC, 区域"
        
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    def import_from_csv(self, file_path):
        """从CSV导入"""
        count = 0
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data = {
                        '合同编号': row.get('合同编号', ''),
                        '项目代码': row.get('项目代码', ''),
                        '对方单位名称': row.get('对方单位名称', ''),
                        '区域': row.get('区域', ''),
                        '合同金额': float(row.get('合同金额', 0) or 0),
                        '合同起始日期': row.get('合同起始日期', ''),
                        '合同终止日期': row.get('合同终止日期', ''),
                        '合同内容': row.get('合同内容', '')
                    }
                    if data['合同编号'] and self.add_contract(data):
                        count += 1
            return count
        except Exception as e:
            raise e


class ContractManagerApp:
    """主应用"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("合同管理系统 v2.0 (轻量版)")
        self.root.geometry("1200x700")
        
        self.db = DatabaseManager()
        
        # 区域列表
        self.regions = ['华北区', '华东区', '华南区', '华中区', '东北区', '西南区', '西北区', '京津区', '国能业务部']
        
        # 合同类型
        self.contract_types = ['维保费', '维修费', '技术服务费', '其他']
        
        self.create_widgets()
        self.load_data()
    
    def create_widgets(self):
        """创建界面"""
        # 创建笔记本（标签页）
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # 合同管理标签页
        contract_frame = ttk.Frame(notebook)
        notebook.add(contract_frame, text='合同管理')
        self.create_contract_tab(contract_frame)
        
        # 年度统计标签页
        yearly_frame = ttk.Frame(notebook)
        notebook.add(yearly_frame, text='年度统计')
        self.create_yearly_tab(yearly_frame)
        
        # 区域统计标签页
        region_frame = ttk.Frame(notebook)
        notebook.add(region_frame, text='区域统计')
        self.create_region_tab(region_frame)
    
    def create_contract_tab(self, parent):
        """合同管理标签页"""
        # 工具栏
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(toolbar, text="添加合同", command=self.add_contract).pack(side='left', padx=2)
        ttk.Button(toolbar, text="添加开票", command=self.add_invoice).pack(side='left', padx=2)
        ttk.Button(toolbar, text="添加回款", command=self.add_payment).pack(side='left', padx=2)
        ttk.Button(toolbar, text="导入CSV", command=self.import_csv).pack(side='left', padx=2)
        ttk.Button(toolbar, text="刷新", command=self.load_data).pack(side='left', padx=2)
        
        # 筛选区
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
        
        # 表格
        columns = ('合同编号', '项目代码', '对方单位', '区域', '合同金额', '起始日期', '终止日期', '合同内容', '累计开票', '累计回款', '应收账款')
        self.contract_tree = ttk.Treeview(parent, columns=columns, show='headings', height=25)
        
        for col in columns:
            self.contract_tree.heading(col, text=col)
            self.contract_tree.column(col, width=100, anchor='center')
        
        self.contract_tree.column('对方单位', width=150)
        self.contract_tree.column('合同金额', width=120)
        self.contract_tree.column('累计开票', width=120)
        self.contract_tree.column('累计回款', width=120)
        self.contract_tree.column('应收账款', width=120)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(parent, orient='vertical', command=self.contract_tree.yview)
        self.contract_tree.configure(yscrollcommand=scrollbar.set)
        
        self.contract_tree.pack(side='left', fill='both', expand=True, padx=5)
        scrollbar.pack(side='right', fill='y', pady=5)
    
    def create_yearly_tab(self, parent):
        """年度统计标签页"""
        # 表格
        columns = ('年度', '合同数', '合同总额', '开票总额', '回款总额', '应收账款')
        self.yearly_tree = ttk.Treeview(parent, columns=columns, show='headings', height=30)
        
        for col in columns:
            self.yearly_tree.heading(col, text=col)
            self.yearly_tree.column(col, width=150, anchor='center')
        
        self.yearly_tree.pack(fill='both', expand=True, padx=10, pady=10)
    
    def create_region_tab(self, parent):
        """区域统计标签页"""
        # 筛选
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(filter_frame, text="年度:").pack(side='left', padx=2)
        self.region_year_filter = ttk.Combobox(filter_frame, width=10, state='readonly')
        self.region_year_filter['values'] = ['全部'] + [str(y) for y in range(2026, 2019, -1)]
        self.region_year_filter.set('全部')
        self.region_year_filter.pack(side='left', padx=2)
        self.region_year_filter.bind('<<ComboboxSelected>>', lambda e: self.load_region_stats())
        
        # 表格
        columns = ('区域', '年度', '合同内容', '合同数', '合同总额', '开票总额', '回款总额')
        self.region_tree = ttk.Treeview(parent, columns=columns, show='headings', height=30)
        
        for col in columns:
            self.region_tree.heading(col, text=col)
            self.region_tree.column(col, width=120, anchor='center')
        
        self.region_tree.pack(fill='both', expand=True, padx=10, pady=10)
    
    def load_data(self):
        """加载数据"""
        year = None if self.year_filter.get() == '全部' else self.year_filter.get()
        region = None if self.region_filter.get() == '全部' else self.region_filter.get()
        
        rows = self.db.get_contracts(year, region)
        
        # 清空表格
        for item in self.contract_tree.get_children():
            self.contract_tree.delete(item)
        
        # 填充数据
        for row in rows:
            contract_no, project_code, company, region, amount, start_date, end_date, content, invoice, payment = row
            receivable = invoice - payment
            self.contract_tree.insert('', 'end', values=(
                contract_no, project_code, company, region, 
                f'{amount:,.2f}' if amount else '0.00',
                start_date or '', end_date or '', content or '',
                f'{invoice:,.2f}', f'{payment:,.2f}', f'{receivable:,.2f}'
            ))
        
        # 加载统计
        self.load_yearly_stats()
        self.load_region_stats()
    
    def load_yearly_stats(self):
        """加载年度统计"""
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
    
    def load_region_stats(self):
        """加载区域统计"""
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
    
    def add_contract(self):
        """添加合同"""
        dialog = tk.Toplevel(self.root)
        dialog.title("添加合同")
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 表单
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
        
        # 起始日期
        ttk.Label(frame, text="起始日期:").grid(row=row, column=0, sticky='e', pady=5)
        fields['起始日期'] = ttk.Entry(frame, width=30)
        fields['起始日期'].insert(0, datetime.now().strftime('%Y-%m-%d'))
        fields['起始日期'].grid(row=row, column=1, pady=5)
        row += 1
        
        # 终止日期
        ttk.Label(frame, text="终止日期:").grid(row=row, column=0, sticky='e', pady=5)
        fields['终止日期'] = ttk.Entry(frame, width=30)
        fields['终止日期'].grid(row=row, column=1, pady=5)
        row += 1
        
        # 合同内容
        ttk.Label(frame, text="合同内容:").grid(row=row, column=0, sticky='e', pady=5)
        fields['合同内容'] = ttk.Combobox(frame, width=27, values=self.contract_types, state='readonly')
        fields['合同内容'].grid(row=row, column=1, pady=5)
        row += 1
        
        # 按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=20)
        
        def save():
            try:
                data = {
                    '合同编号': fields['合同编号'].get().strip(),
                    '项目代码': fields['项目代码'].get().strip(),
                    '对方单位名称': fields['对方单位'].get().strip(),
                    '区域': fields['区域'].get(),
                    '合同金额': float(fields['合同金额'].get().strip() or 0),
                    '合同起始日期': fields['起始日期'].get().strip(),
                    '合同终止日期': fields['终止日期'].get().strip(),
                    '合同内容': fields['合同内容'].get()
                }
                
                if not data['合同编号']:
                    messagebox.showwarning("警告", "合同编号不能为空")
                    return
                
                if self.db.add_contract(data):
                    messagebox.showinfo("成功", "合同添加成功")
                    dialog.destroy()
                    self.load_data()
                else:
                    messagebox.showwarning("警告", "合同编号已存在")
            except ValueError:
                messagebox.showwarning("警告", "合同金额必须是数字")
        
        ttk.Button(btn_frame, text="保存", command=save).pack(side='left', padx=10)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side='left', padx=10)
    
    def add_invoice(self):
        """添加开票"""
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
        date_entry = ttk.Entry(frame, width=25)
        date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        date_entry.grid(row=1, column=1, pady=5)
        
        ttk.Label(frame, text="开票金额:").grid(row=2, column=0, sticky='e', pady=5)
        amount_entry = ttk.Entry(frame, width=25)
        amount_entry.grid(row=2, column=1, pady=5)
        
        def save():
            try:
                amount = float(amount_entry.get().strip())
                date = date_entry.get().strip()
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
        """添加回款"""
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
        date_entry = ttk.Entry(frame, width=25)
        date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        date_entry.grid(row=1, column=1, pady=5)
        
        ttk.Label(frame, text="回款金额:").grid(row=2, column=0, sticky='e', pady=5)
        amount_entry = ttk.Entry(frame, width=25)
        amount_entry.grid(row=2, column=1, pady=5)
        
        def save():
            try:
                amount = float(amount_entry.get().strip())
                date = date_entry.get().strip()
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
    
    def import_csv(self):
        """导入CSV"""
        file_path = filedialog.askopenfilename(
            title="选择CSV文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            count = self.db.import_from_csv(file_path)
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
