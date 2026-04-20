import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import random

# --- 1. 终端配置 ---
st.set_page_config(page_title="NIQING | 多维信号终端", layout="wide")
st.markdown("<style>.stApp { background-color: #0b0e14; color: #e0e0e0; }</style>", unsafe_allow_html=True)

# --- 2. 授权验证 ---
if "auth" not in st.session_state:
    st.markdown("<h2 style='text-align: center; color: #d4af37;'>NIQING STUDIO 策略终端</h2>", unsafe_allow_html=True)
    if st.text_input("授权令牌", type="password") == "niqing888":
        st.session_state.auth = True
        st.rerun()
    st.stop()

# --- 3. 核心算法引擎 ---
class NIQINGEngine:
    @staticmethod
    def is_green_cross(row, sens=0.15):
        """判定绿色十字星逻辑"""
        # 1. 必须是阴线 (开盘 > 收盘)
        is_down = row['今开'] > row['最新价']
        # 2. 实体极小 (十字星)
        entity = abs(row['今开'] - row['最新价'])
        total_range = row['最高'] - row['最低'] + 0.001
        is_cross = (entity / total_range) <= sens
        return is_down and is_cross

    @staticmethod
    def is_kdj_golden(code):
        """判定KDJ金叉逻辑"""
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(30)
            if len(df) < 10: return False
            low_9, high_9 = df['最低'].rolling(9).min(), df['最高'].rolling(9).max()
            rsv = (df['收盘'] - low_9) / (high_9 - low_9 + 0.001) * 100
            df['K'] = rsv.ewm(com=2, adjust=False).mean()
            df['D'] = df['K'].ewm(com=2, adjust=False).mean()
            return (df.iloc[-2]['K'] < df.iloc[-2]['D']) and (df.iloc[-1]['K'] > df.iloc[-1]['D'])
        except: return False

# --- 4. UI 交互布局 ---
st.title("妮情 · 双模信号雷达")

with st.sidebar:
    st.header("⚙️ 扫描配置")
    scan_limit = st.slider("扫描活跃股数量", 50, 500, 150)
    cross_sens = st.slider("十字星灵敏度", 0.05, 0.3, 0.15, help="越小越像标准的十字")
    min_vol = st.number_input("最小成交额(万)", value=8000)

if st.button("🚀 启动全市场深度双模扫描"):
    with st.spinner("同步实时数据中..."):
        all_data = ak.stock_zh_a_spot_em()
        all_data[['最新价', '涨跌幅', '成交额', '最高', '最低', '今开']] = all_data[['最新价', '涨跌幅', '成交额', '最高', '最低', '今开']].apply(pd.to_numeric, errors='coerce')
        
        # 筛选活跃股票池
        active_pool = all_data[all_data['成交额'] >= min_vol * 10000].sort_values('成交额', ascending=False).head(scan_limit)
        
        golden_res, cross_res = [], []
        bar = st.progress(0)
        status = st.empty()

        for i, (idx, row) in enumerate(active_pool.iterrows()):
            status.text(f"正在分析 ({i+1}/{len(active_pool)}): {row['名称']}")
            
            # 1. 检测十字星 (实时数据即可判定)
            if NIQINGEngine.is_green_cross(row, cross_sens):
                cross_res.append({"代码": row['代码'], "名称": row['名称'], "涨跌幅": row['涨跌幅'], "成交额(亿)": round(row['成交额']/1e8, 2)})
            
            # 2. 检测金叉 (需要历史数据)
            if NIQINGEngine.is_kdj_golden(row['代码']):
                golden_res.append({"代码": row['代码'], "名称": row['名称'], "最新价": row['最新价'], "涨跌幅": row['涨跌幅']})
            
            bar.progress((i + 1) / len(active_pool))
            time.sleep(0.05) # 基础频率保护
        
        st.session_state.g_list = pd.DataFrame(golden_res)
        st.session_state.c_list = pd.DataFrame(cross_res)
        status.success("全市场双模扫描已完成！")

# --- 5. 双窗口结果展示 ---
col1, col2 = st.columns(2)

with col1:
    st.markdown("### 📈 今日 KDJ 金叉股")
    if "g_list" in st.session_state and not st.session_state.g_list.empty:
        st.dataframe(st.session_state.g_list, use_container_width=True, height=400)
    else:
        st.info("暂无金叉信号")

with col2:
    st.markdown("### 💹 今日绿色十字星")
    if "c_list" in st.session_state and not st.session_state.c_list.empty:
        # 绿色十字星用绿色字体装饰下（可选）
        st.dataframe(st.session_state.c_list, use_container_width=True, height=400)
    else:
        st.info("暂无十字星信号")

# --- 6. 综合研判图表 ---
if ("g_list" in st.session_state and not st.session_state.g_list.empty) or \
   ("c_list" in st.session_state and not st.session_state.c_list.empty):
    
    st.divider()
    st.subheader("🔍 选定个股深度透视")
    
    # 合并两个列表供用户选择查看
    all_names = []
    if "g_list" in st.session_state: all_names += st.session_state.g_list['名称'].tolist()
    if "c_list" in st.session_state: all_names += st.session_state.c_list['名称'].tolist()
    
    view_stock = st.selectbox("选择股票查看 K 线形态确认", list(set(all_names)))
    
    if view_stock:
        # 获取代码
        lookup = pd.concat([st.session_state.get('g_list', pd.DataFrame()), st.session_state.get('c_list', pd.DataFrame())])
        target_code = lookup[lookup['名称'] == view_stock]['代码'].values[0]
        
        h_df = ak.stock_zh_a_hist(symbol=target_code, adjust="qfq").tail(60)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
        fig.add_trace(go.Candlestick(x=h_df['日期'], open=h_df['开盘'], high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'], name="K线"), row=1, col=1)
        fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
