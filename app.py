import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import random

# --- 1. 终端全局配置 ---
st.set_page_config(page_title="NIQING | 量能雷达终端", layout="wide")
st.markdown("<style>.stApp { background-color: #0b0e14; color: #e0e0e0; }</style>", unsafe_allow_html=True)

# 核心：初始化 session_state 确保字段永远存在
for key in ['g_list', 'c_list']:
    if key not in st.session_state:
        st.session_state[key] = pd.DataFrame(columns=['代码', '名称', '涨跌幅%', '最新价', '成交量(手)', '成交额(亿)'])

# --- 2. 增强型策略引擎 ---
class NIQINGEngine:
    @staticmethod
    def safe_api_call(func, **kwargs):
        """防封锁：带随机延迟的 API 调用"""
        for i in range(3):
            try:
                time.sleep(random.uniform(0.3, 0.7))
                return func(**kwargs)
            except:
                time.sleep(i + 1)
        return pd.DataFrame()

    @staticmethod
    def check_signals(row, sens):
        """同步判定十字星与基本形态"""
        try:
            o, c, h, l = row['今开'], row['最新价'], row['最高'], row['最低']
            is_cross = (o > c) and (abs(o - c) / (h - l + 0.001) <= sens)
            return is_cross
        except: return False

# --- 3. 侧边栏与主界面 ---
st.title("妮情 · 量能信号全自动实时雷达")

with st.sidebar:
    st.header("⚙️ 策略参数")
    scan_count = st.slider("扫描深度", 50, 300, 100)
    cross_sens = st.slider("十字星灵敏度", 0.05, 0.4, 0.15)
    min_vol = st.number_input("准入成交额(万)", value=10000)

if st.button("🚀 启动全市场深度量能扫描"):
    with st.spinner("正在同步实时盘面数据..."):
        # 获取实时行情
        raw_df = NIQINGEngine.safe_api_call(ak.stock_zh_a_spot_em)
        if not raw_df.empty:
            # 强制格式化数值列
            val_cols = ['最新价', '涨跌幅', '成交量', '成交额', '最高', '最低', '今开']
            raw_df[val_cols] = raw_df[val_cols].apply(pd.to_numeric, errors='coerce')
            
            # 过滤高活跃池
            pool = raw_df[raw_df['成交额'] >= min_vol * 10000].sort_values('成交额', ascending=False).head(scan_count)
            
            g_data, c_data = [], []
            progress = st.progress(0)
            
            for i, (idx, row) in enumerate(pool.iterrows()):
                # 统一构建基础信息字典
                base_info = {
                    "代码": row['代码'], "名称": row['名称'], "涨跌幅%": row['涨跌幅'],
                    "最新价": row['最新价'], "成交量(手)": int(row['成交量']),
                    "成交额(亿)": round(row['成交额'] / 1e8, 2)
                }
                
                # 判定十字星
                if NIQINGEngine.check_signals(row, cross_sens):
                    c_data.append(base_info)
                
                # 判定 KDJ 金叉 (此处为逻辑演示，可根据需要开启)
                # if i % 10 == 0: g_data.append(base_info) 
                
                progress.progress((i + 1) / len(pool))
            
            st.session_state.g_list = pd.DataFrame(g_data) if g_data else st.session_state.g_list
            st.session_state.c_list = pd.DataFrame(c_data) if c_data else st.session_state.c_list
            st.success("量能扫描完成！")

# --- 4. 结果矩阵展示 ---
col1, col2 = st.columns(2)
with col1:
    st.markdown("### 📈 KDJ 金叉监控")
    st.dataframe(st.session_state.g_list, use_container_width=True, height=350)
with col2:
    st.markdown("### 💹 绿色十字星监控")
    st.dataframe(st.session_state.c_list, use_container_width=True, height=350)

# --- 5. 深度量价回测 (修复 KeyError 关键区) ---
st.divider()
st.subheader("🔍 选定个股深度量价透视")

# 修复：安全合并所有选股名称
current_names = []
if not st.session_state.g_list.empty: current_names += st.session_state.g_list['名称'].tolist()
if not st.session_state.c_list.empty: current_names += st.session_state.c_list['名称'].tolist()
current_names = list(set(current_names))

if current_names:
    target = st.selectbox("选择目标个股进行量价回溯", current_names)
    
    # 获取对应代码
    all_res = pd.concat([st.session_state.g_list, st.session_state.c_list]).drop_duplicates('名称')
    t_code = all_res[all_res['名称'] == target]['代码'].values[0]
    
    h_data = NIQINGEngine.safe_api_call(ak.stock_zh_a_hist, symbol=t_code, adjust="qfq")
    if not h_data.empty:
        h_data = h_data.tail(60)
        # 绘图逻辑：确保列名严格对应 akshare 的中文返回
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
        fig.add_trace(go.Candlestick(x=h_data['日期'], open=h_data['开盘'], high=h_data['最高'], low=h_data['最低'], close=h_data['收盘'], name="K线"), row=1, col=1)
        v_colors = ['#2ecc71' if c > o else '#e74c3c' for c, o in zip(h_data['收盘'], h_data['开盘'])]
        fig.add_trace(go.Bar(x=h_data['日期'], y=h_data['成交量'], marker_color=v_colors, name="成交量"), row=2, col=1)
        fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("完成上方扫描后，此处将自动开启深度量价透视。")
