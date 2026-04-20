import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import random

# --- 1. 终端配置 ---
st.set_page_config(page_title="NIQING | 量能雷达", layout="wide")
st.markdown("<style>.stApp { background-color: #0b0e14; color: #e0e0e0; }</style>", unsafe_allow_html=True)

# 初始化状态，防止空值报错
if "g_list" not in st.session_state: st.session_state.g_list = pd.DataFrame()
if "c_list" not in st.session_state: st.session_state.c_list = pd.DataFrame()

# --- 2. 授权验证 ---
if "auth" not in st.session_state:
    st.markdown("<h2 style='text-align: center; color: #d4af37;'>NIQING STUDIO 策略终端</h2>", unsafe_allow_html=True)
    if st.text_input("授权令牌", type="password") == "niqing888":
        st.session_state.auth = True
        st.rerun()
    st.stop()

# --- 3. 核心计算类 ---
class NIQINGEngine:
    @staticmethod
    def safe_fetch(func, **kwargs):
        for _ in range(3):
            try:
                time.sleep(random.uniform(0.1, 0.3))
                return func(**kwargs)
            except: time.sleep(1)
        return pd.DataFrame()

    @staticmethod
    def is_green_cross(row, sens):
        # 绿色十字星：阴线 (开盘 > 收盘) 且 实体比例小
        if row['今开'] <= row['最新价']: return False
        entity = abs(row['今开'] - row['最新价'])
        v_range = row['最高'] - row['最低'] + 0.001
        return (entity / v_range) <= sens

    @staticmethod
    def check_kdj(code):
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(20)
            if len(df) < 10: return False
            # 必须使用中文列名计算
            low_9, high_9 = df['最低'].rolling(9).min(), df['最高'].rolling(9).max()
            rsv = (df['收盘'] - low_9) / (high_9 - low_9 + 0.001) * 100
            df['K'] = rsv.ewm(com=2, adjust=False).mean()
            df['D'] = df['K'].ewm(com=2, adjust=False).mean()
            return (df.iloc[-2]['K'] < df.iloc[-2]['D']) and (df.iloc[-1]['K'] > df.iloc[-1]['D'])
        except: return False

# --- 4. 界面布局 ---
st.title("妮情 · 量能信号实时全自动雷达")

with st.sidebar:
    st.header("⚙️ 扫描配置")
    scan_limit = st.slider("扫描活跃股数量", 50, 300, 100)
    cross_sens = st.slider("十字星灵敏度", 0.05, 0.4, 0.15)
    min_vol_val = st.number_input("最小成交额(万)", value=10000)

if st.button("🚀 启动全市场【量能+形态】深度扫描"):
    with st.spinner("同步实时数据并分析量能中..."):
        all_data = ak.stock_zh_a_spot_em()
        # 字段强制转换
        cols = ['最新价', '涨跌幅', '成交量', '成交额', '最高', '最低', '今开']
        all_data[cols] = all_data[cols].apply(pd.to_numeric, errors='coerce')
        
        # 筛选活跃池
        pool = all_data[all_data['成交额'] >= min_vol_val * 10000].sort_values('成交额', ascending=False).head(scan_limit)
        
        g_res, c_res = [], []
        bar = st.progress(0)
        
        for i, (idx, row) in enumerate(pool.iterrows()):
            info = {
                "代码": row['代码'], "名称": row['名称'], 
                "涨跌幅%": row['涨跌幅'], "最新价": row['最新价'],
                "成交量(手)": int(row['成交量']), 
                "成交额(亿)": round(row['成交额']/1e8,
