import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import random

# --- 1. 终端基础配置 ---
st.set_page_config(page_title="NIQING | 量能雷达", layout="wide")
st.markdown("<style>.stApp { background-color: #0b0e14; color: #e0e0e0; }</style>", unsafe_allow_html=True)

# 初始化 session_state
if "g_list" not in st.session_state: st.session_state.g_list = pd.DataFrame()
if "c_list" not in st.session_state: st.session_state.c_list = pd.DataFrame()

# --- 2. 核心计算逻辑 ---
class NIQINGEngine:
    @staticmethod
    def is_green_cross(row, sens):
        """判定绿色十字星：阴线且实体极小"""
        try:
            o, c, h, l = row['今开'], row['最新价'], row['最高'], row['最低']
            if o <= c: return False  # 必须是阴线
            entity = abs(o - c)
            v_range = h - l + 0.001
            return (entity / v_range) <= sens
        except: return False

    @staticmethod
    def get_kdj_signal(code):
        """判定 KDJ 金叉"""
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(20)
            if len(df) < 10: return False
            low_9, high_9 = df['最低'].rolling(9).min(), df['最高'].rolling(9).max()
            rsv = (df['收盘'] - low_9) / (high_9 - low_9 + 0.001) * 100
            df['K'] = rsv.ewm(com=2, adjust=False).mean()
            df['D'] = df['K'].ewm(com=2, adjust=False).mean()
            return (df.iloc[-2]['K'] < df.iloc[-2]['D']) and (df.iloc[-1]['K'] > df.iloc[-1]['D'])
        except: return False

# --- 3. UI 交互 ---
st.title("妮情 · 全自动量能雷达终端")

with st.sidebar:
    st.header("⚙️ 扫描配置")
    scan_limit = st.slider("扫描股数", 50, 200, 100)
    cross_sens = st.slider("十字星灵敏度", 0.05, 0.3, 0.15)
    min_vol_val = st.number_input("最小成交额(万)", value=10000)

if st.button("🚀 启动全市场深度扫描"):
    with st.spinner("同步数据中..."):
        all_data = ak.stock_zh_a_spot_em()
        if not all_data.empty:
            # 字段预处理
            cols = ['最新价', '涨跌幅', '成交量', '成交额', '最高', '最低', '今开']
            all_data[cols] = all_data[cols].apply(pd.to_numeric, errors='coerce')
            
            pool = all_data[all_data['成交额'] >= min_vol_val * 10000].sort_values('成交额', ascending=False).head(scan_limit)
            
            g_res, c_res = [], []
            bar = st.progress(0)
            
            for i, (idx, row) in enumerate(pool.iterrows()):
                # 修复 SyntaxError：确保字典括号完全配对
                info = {
                    "代码": row['代码'], 
                    "名称": row['名称'], 
                    "涨跌幅%": row['涨跌幅'], 
                    "最新价": row['最新价'],
                    "成交量(手)": int(row['成交量']), 
                    "成交额(亿)": round(float(row['成交额']) / 100000000, 2)
                }
                
                if NIQINGEngine.is_green_cross(row, cross_sens): c_res.append(info)
                if NIQINGEngine.get_kdj_signal(row['代码']): g_res.append(info)
                bar.progress((i + 1) / len(pool))
            
            st.session_state.g_list = pd.DataFrame(g_res)
            st.session_state.c_list = pd.DataFrame(c_res)
            st.success("分析完毕")

# --- 4. 结果展示 ---
col_l, col_r = st.columns(2)
with col_l:
    st.markdown("### 📈 KDJ 金叉股")
    st.dataframe(st.session_state.g_list, use_container_width=True)
with col_r:
    st.markdown("### 💹 绿色十字星")
    st.dataframe(st.session_state.c_list, use_container_width=True)

# --- 5. 深度量价回测 (彻底修复 KeyError) ---
st.divider()
all_df = pd.concat([st.session_state.g_list, st.session_state.c_list]).drop_duplicates(subset=['名称'])

if not all_df.empty:
    selected_name = st.selectbox("🔍 选择个股查看量价配合", all_df['名称'].tolist())
    target_code = all_df[all_df['名称'] == selected_name]['代码'].values[0]
    
    with st.spinner("绘制回测图表..."):
        h_df = ak.stock_zh_a_hist(symbol=target_code, adjust="qfq").tail(60)
        
        # 严格使用中文列名引用
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        
        # K线主图
        fig.add_trace(go.Candlestick(
            x=h_df['日期'], open=h_df['开盘'], high=h_df['最高'], 
            low=h_df['最低'], close=h_df['收盘'], name="K线"
        ), row=1, col=1)
        
        # 成交量副图
        v_colors = ['#2ecc71' if c > o else '#e74c3c' for c, o in zip(h_df['收盘'], h_df['开盘'])]
        fig.add_trace(go.Bar(x=h_df['日期'], y=h_df['成交量'], marker_color=v_colors, name="成交量"), row=2, col=1)
        
        fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("执行扫描后获取数据")
