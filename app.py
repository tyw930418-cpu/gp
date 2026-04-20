import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import random

# --- 1. 终端配置 ---
st.set_page_config(page_title="NIQING | 智能搜索雷达", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0b0e14; color: #e0e0e0; }
    .stButton>button { border: 1px solid #d4af37; color: #d4af37; background: transparent; width: 100%; }
    .stButton>button:hover { background-color: #d4af37; color: black; }
    .search-box { border: 1px solid #d4af37 !important; }
    </style>
    """, unsafe_allow_html=True)

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
                time.sleep(random.uniform(0.2, 0.5))
                return func(**kwargs)
            except:
                time.sleep(1)
        return pd.DataFrame()

    @staticmethod
    def calc_kdj(df):
        if df.empty: return df
        low_9 = df['最低'].rolling(9).min()
        high_9 = df['最高'].rolling(9).max()
        rsv = (df['收盘'] - low_9) / (high_9 - low_9 + 0.001) * 100
        df['K'] = rsv.ewm(com=2, adjust=False).mean()
        df['D'] = df['K'].ewm(com=2, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']
        return df

# --- 4. UI 交互布局 ---
st.title("妮情 · 全市场搜索与金叉预警")

# 侧边栏：搜索逻辑
st.sidebar.markdown("### 🔍 选股雷达")
mode = st.sidebar.radio("选择模式", ["关键词搜索", "行业分类"])

if mode == "关键词搜索":
    search_query = st.sidebar.text_input("输入关键词 (如：商业航天)", "商业航天")
    if st.sidebar.button("🔍 全市场匹配"):
        with st.spinner(f"正在全市场匹配 '{search_query}' 相关股票..."):
            # 获取全 A 股快照
            all_stocks = NIQINGEngine.safe_fetch(ak.stock_zh_a_spot_em)
            if not all_stocks.empty:
                # 模糊匹配名称
                res = all_stocks[all_stocks['名称'].str.contains(search_query, na=False)]
                if res.empty:
                    st.sidebar.warning("未匹配到名称包含该词的股票")
                else:
                    st.session_state.ind_data = res[['代码', '名称', '最新价', '涨跌幅']]
            else:
                st.sidebar.error("数据源连接失败")

else:
    industry_list = ["航天航空", "半导体", "通信设备", "汽车整车", "酿酒行业", "生物制品"]
    selected_industry = st.sidebar.selectbox("选择目标行业", industry_list)
    if st.sidebar.button("🔄 同步行业数据"):
        with st.spinner("获取中..."):
            df_ind = NIQINGEngine.safe_fetch(ak.stock_board_industry_cons_em, symbol=selected_industry)
            if not df_ind.empty:
                st.session_state.ind_data = df_ind[['代码', '名称', '最新价', '涨跌幅']]
            else:
                st.sidebar.error("同步失败")

# 主界面显示
col_list, col_chart = st.columns([1, 2.5])

with col_list:
    if "ind_data" in st.session_state:
        st.markdown(f"#### 📋 匹配结果 ({len(st.session_state.ind_data)})")
        stock_options = st.session_state.ind_data['名称'].tolist()
        selected_stock_name = st.selectbox("选择目标个股", stock_options)
        target_code = st.session_state.ind_data[st.session_state.ind_data['名称'] == selected_stock_name]['代码'].values[0]
        
        row = st.session_state.ind_data[st.session_state.ind_data['名称'] == selected_stock_name].iloc[0]
        st.metric("最新价", f"¥{row['最新价']}", f"{row['涨跌幅']}%")
    else:
        st.info("请先通过侧边栏执行搜索或同步")
        target_code = None

with col_chart:
    if target_code:
        st.markdown(f"#### 📊 {selected_stock_name} ({target_code}) 深度监测")
        with st.spinner("分析 KDJ 走势..."):
            h_df = NIQINGEngine.safe_fetch(ak.stock_zh_a_hist, symbol=target_code, adjust="qfq")
            if not h_df.empty:
                h_df = NIQINGEngine.calc_kdj(h_df)
                last = h_df.iloc[-1]
                prev = h_df.iloc[-2]
                is_golden = (prev['K'] < prev['D']) and (last['K'] > last['D'])
                
                if is_golden:
                    st.markdown(f"""
                        <div style="padding:15px; background:rgba(46, 204, 113, 0.2); border:1px solid #2ecc71; border-radius:10px; text-align:center; margin-bottom:15px;">
                            <h2 style="color:#2ecc71; margin:0;">🔥 金叉信号已达成！</h2>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("<div style='text-align:center; color:#888;'>趋势平稳中</div>", unsafe_allow_html=True)

                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
                fig.add_trace(go.Candlestick(x=h_df['日期'], open=h_df['开盘'], high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'], name="K线"), row=1, col=1)
                fig.add_trace(go.Scatter(x=h_df['日期'], y=h_df['J'], line=dict(color='purple', width=2), name="KDJ-J"), row=2, col=1)
                fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
