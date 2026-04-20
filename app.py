import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import random

# --- 1. 终端配置与状态初始化 ---
st.set_page_config(page_title="NIQING | 量能实时雷达", layout="wide")
st.markdown("<style>.stApp { background-color: #0b0e14; color: #e0e0e0; }</style>", unsafe_allow_html=True)

if "g_list" not in st.session_state: st.session_state.g_list = pd.DataFrame()
if "c_list" not in st.session_state: st.session_state.c_list = pd.DataFrame()

# --- 2. 核心抗干扰引擎 ---
class NIQINGEngine:
    @staticmethod
    def safe_fetch(func, **kwargs):
        """防止 ConnectionError：增加随机延迟与 3 次重试逻辑"""
        for i in range(3):
            try:
                time.sleep(random.uniform(0.2, 0.5))
                df = func(**kwargs)
                if df is not None and not df.empty:
                    return df
            except:
                time.sleep(i + 1)
        return pd.DataFrame()

    @staticmethod
    def is_green_cross(row, sens):
        """判定绿色十字星：阴线且实体占比极小"""
        try:
            o, c, h, l = row['今开'], row['最新价'], row['最高'], row['最低']
            if o <= c: return False 
            entity = abs(o - c)
            v_range = h - l + 0.001
            return (entity / v_range) <= sens
        except: return False

    @staticmethod
    def check_kdj_gold(code):
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

# --- 3. 界面布局 ---
st.title("妮情 · 量能信号实时全自动雷达")

with st.sidebar:
    st.header("⚙️ 扫描配置")
    scan_limit = st.slider("扫描股数", 50, 200, 100)
    cross_sens = st.slider("十字星灵敏度", 0.05, 0.3, 0.15)
    min_vol_val = st.number_input("最小成交额(万)", value=10000)

if st.button("🚀 启动全市场量能深度扫描"):
    with st.spinner("同步实时行情数据..."):
        all_data = NIQINGEngine.safe_fetch(ak.stock_zh_a_spot_em)
        if not all_data.empty:
            # 数值类型强制转换
            cols = ['最新价', '涨跌幅', '成交量', '成交额', '最高', '最低', '今开']
            all_data[cols] = all_data[cols].apply(pd.to_numeric, errors='coerce')
            
            pool = all_data[all_data['成交额'] >= min_vol_val * 10000].sort_values('成交额', ascending=False).head(scan_limit)
            
            g_res, c_res = [], []
            bar = st.progress(0)
            
            for i, (idx, row) in enumerate(pool.iterrows()):
                # 核心字段对齐，包含成交量
                info = {
                    "代码": row['代码'], "名称": row['名称'], "涨跌幅%": row['涨跌幅'],
                    "最新价": row['最新价'], "成交量(手)": int(row['成交量']),
                    "成交额(亿)": round(float(row['成交额']) / 100000000, 2)
                }
                
                if NIQINGEngine.is_green_cross(row, cross_sens): c_res.append(info)
                if NIQINGEngine.check_kdj_gold(row['代码']): g_res.append(info)
                bar.progress((i + 1) / len(pool))
            
            st.session_state.g_list = pd.DataFrame(g_res)
            st.session_state.c_list = pd.DataFrame(c_res)
            st.success("扫描完成")

# --- 4. 结果双屏与深度回测 ---
c1, c2 = st.columns(2)
with c1:
    st.markdown("### 📈 KDJ 金叉 (带量能)")
    st.dataframe(st.session_state.g_list, use_container_width=True)
with c2:
    st.markdown("### 💹 绿色十字星 (带量能)")
    st.dataframe(st.session_state.c_list, use_container_width=True)

st.divider()
all_names = list(set(st.session_state.g_list['名称'].tolist() + st.session_state.c_list['名称'].tolist())) if not (st.session_state.g_list.empty and st.session_state.c_list.empty) else []

if all_names:
    selected = st.selectbox("🔍 选定个股量价透视", all_names)
    combined = pd.concat([st.session_state.g_list, st.session_state.c_list])
    target_code = combined[combined['名称'] == selected]['代码'].values[0]
    
    h_df = NIQINGEngine.safe_fetch(ak.stock_zh_a_hist, symbol=target_code, adjust="qfq").tail(60)
    
    # 绘图：修复 KeyError 关键点，严格使用中文列名
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    fig.add_trace(go.Candlestick(x=h_df['日期'], open=h_df['开盘'], high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'], name="K线"), row=1, col=1)
    
    # 量能柱状图
    v_colors = ['#2ecc71' if c > o else '#e74c3c' for c, o in zip(h_df['收盘'], h_df['开盘'])]
    fig.add_trace(go.Bar(x=h_df['日期'], y=h_df['成交量'], marker_color=v_colors, name="成交量"), row=2, col=1)
    
    fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)
