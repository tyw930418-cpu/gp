import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import random
from datetime import datetime

# --- 1. 终端品牌与配置 ---
st.set_page_config(page_title="NIQING | 抗干扰雷达终端", layout="wide")
st.markdown("<style>.stApp { background-color: #0b0e14; color: #e0e0e0; }</style>", unsafe_allow_html=True)

# --- 2. 授权检查 ---
if "auth" not in st.session_state:
    st.markdown("<h2 style='text-align: center; color: #d4af37;'>NIQING STUDIO 智能终端</h2>", unsafe_allow_html=True)
    if st.text_input("授权令牌", type="password") == "niqing888":
        st.session_state.auth = True
        st.rerun()
    st.stop()

# --- 3. 稳健型计算引擎 ---
class RobustEngine:
    @staticmethod
    def safe_fetch(func, *args, **kwargs):
        """抗干扰抓取核心：错误拦截 + 自动重试"""
        for i in range(3): # 最多重试3次
            try:
                # 增加一个 0.5-1.5秒的随机延迟，降低封锁概率
                time.sleep(random.uniform(0.5, 1.5)) 
                data = func(*args, **kwargs)
                if data is not None and not data.empty:
                    return data
            except Exception as e:
                if i == 2: # 最后一次尝试也失败了
                    return pd.DataFrame()
                time.sleep(2)
        return pd.DataFrame()

    @staticmethod
    def calc_kdj(df):
        low_list = df['最低'].rolling(9).min()
        high_list = df['最高'].rolling(9).max()
        rsv = (df['收盘'] - low_list) / (high_list - low_list) * 100
        df['K'] = rsv.ewm(com=2, adjust=False).mean()
        df['D'] = df['K'].ewm(com=2, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']
        return df

# --- 4. 实时监控大厅 ---
st.title("妮情 · A股抗干扰实时雷达")

tab1, tab2 = st.tabs(["📡 实时监控大厅", "📈 深度指标回测"])

with tab1:
    c1, c2 = st.columns([1, 4])
    with c1:
        is_live = st.toggle("开启实时雷达", value=False)
        rate = st.select_slider("刷新频率 (秒)", options=[30, 60, 120, 300], value=60)
    
    status_bar = st.empty()
    data_display = st.empty()

    while is_live:
        now = datetime.now().strftime("%H:%M:%S")
        status_bar.info(f"正在同步数据... (最后尝试: {now})")
        
        # 使用安全抓取
        raw_df = RobustEngine.safe_fetch(ak.stock_zh_a_spot_em)
        
        if not raw_df.empty:
            raw_df[['最新价', '今开', '最高', '最低', '成交额']] = raw_df[['最新价', '今开', '最高', '最低', '成交额']].apply(pd.to_numeric, errors='coerce')
            # 这里的过滤逻辑保持你之前的阴线十字星
            raw_df['entity_pct'] = (raw_df['今开'] - raw_df['最新价']).abs() / (raw_df['最高'] - raw_df['最低'] + 0.001)
            mask = (raw_df['最新价'] < raw_df['今开']) & (raw_df['entity_pct'] < 0.2) & (raw_df['成交额'] > 50000000)
            
            res = raw_df[mask].copy()
            status_bar.success(f"🟢 监控中 | 更新时间: {now} | 捕获信号: {len(res)}")
            data_display.dataframe(res.sort_values('成交额', ascending=False), use_container_width=True, height=500)
            if not res.empty: st.toast("捕获新信号！")
        else:
            status_bar.warning(f"🟡 网络波动中，正在等待下一轮重连... (最后尝试: {now})")
            
        time.sleep(rate)
        if not is_live: break

with tab2:
    code = st.text_input("输入代码深度分析", "600519")
    if code:
        # 同样使用安全抓取获取历史数据
        h_df = RobustEngine.safe_fetch(ak.stock_zh_a_hist, symbol=code, period="daily", adjust="qfq")
        if not h_df.empty:
            h_df = RobustEngine.calc_kdj(h_df)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.6, 0.4])
            fig.add_trace(go.Candlestick(x=h_df['日期'], open=h_df['开盘'], high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'], name="K线"), row=1, col=1)
            fig.add_trace(go.Scatter(x=h_df['日期'], y=h_df['J'], line=dict(color='purple'), name="KDJ-J"), row=2, col=1)
            fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("无法连接到数据源，请检查代码或稍后再试。")
