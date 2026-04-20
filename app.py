import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from datetime import datetime

# ==========================================
# 1. 终端视觉配置 (NIQING STUDIO 风格)
# ==========================================
st.set_page_config(page_title="NIQING | 实时金叉雷达", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0b0e14; color: #e0e0e0; }
    .status-box { padding: 10px; border-radius: 5px; border: 1px solid #d4af37; background: #1a1c23; }
    [data-testid="stMetricValue"] { color: #d4af37 !important; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 授权与安全
# ==========================================
if "auth" not in st.session_state:
    st.markdown("<h2 style='text-align: center; color: #d4af37;'>NIQING STUDIO 智能终端</h2>", unsafe_allow_html=True)
    pwd = st.text_input("授权令牌", type="password")
    if pwd == "niqing888":
        st.session_state.auth = True
        st.rerun()
    st.stop()

# ==========================================
# 3. 核心算法引擎
# ==========================================
class RadarEngine:
    @staticmethod
    def calc_indicators(df):
        # KDJ计算
        low_list = df['最低'].rolling(9).min()
        high_list = df['最高'].rolling(9).max()
        rsv = (df['收盘'] - low_list) / (high_list - low_list) * 100
        df['K'] = rsv.ewm(com=2, adjust=False).mean()
        df['D'] = df['K'].ewm(com=2, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']
        # MACD计算
        df['dif'] = df['收盘'].ewm(span=12, adjust=False).mean() - df['收盘'].ewm(span=26, adjust=False).mean()
        df['dea'] = df['dif'].ewm(span=9, adjust=False).mean()
        return df

    @classmethod
    def quick_scan(cls):
        """实时扫描快照"""
        try:
            df = ak.stock_zh_a_spot_em()
            if df.empty: return pd.DataFrame()
            df[['最新价', '今开', '最高', '最低', '成交额']] = df[['最新价', '今开', '最高', '最低', '成交额']].apply(pd.to_numeric)
            
            # 实时形态过滤：阴线十字星 + 活跃成交
            df['entity_pct'] = (df['今开'] - df['最新价']).abs() / (df['最高'] - df['最低'])
            mask = (df['最新价'] < df['今开']) & (df['entity_pct'] < 0.2) & (df['成交额'] > 50000000)
            
            res = df[mask].copy()
            return res[['代码', '名称', '最新价', '涨跌幅', '成交额']]
        except:
            return pd.DataFrame()

# ==========================================
# 4. 界面展示布局
# ==========================================
st.title("妮情 · A股全自动实时雷达")

tab1, tab2 = st.tabs(["📡 实时监控大厅", "📈 深度指标回测"])

with tab1:
    col_ctrl1, col_ctrl2 = st.columns([1, 4])
    with col_ctrl1:
        is_live = st.toggle("开启实时监控", value=False)
        refresh_rate = st.select_slider("刷新频率 (秒)", options=[10, 30, 60, 300], value=60)
    
    # 动态容器
    status_bar = st.empty()
    data_table = st.empty()

    if is_live:
        while is_live:
            current_time = datetime.now().strftime("%H:%M:%S")
            status_bar.markdown(f"🟢 **实时模式已开启** | 最后更新：{current_time} | 频率：{refresh_rate}s")
            
            results = RadarEngine.quick_scan()
            if not results.empty:
                data_table.dataframe(results.sort_values('成交额', ascending=False), use_container_width=True, height=500)
                # 针对新出现的信号弹窗 (这里取第一名作为示例)
                st.toast(f"发现 {len(results)} 个潜在信号", icon="🔍")
            else:
                data_table.info("正在搜索信号中...")
            
            time.sleep(refresh_rate)
            if not is_live: break
    else:
        status_bar.markdown("⚪ **监控已停止** | 点击上方开关启动自动刷新")
        if st.button("单次手动扫描"):
            results = RadarEngine.quick_scan()
            data_table.dataframe(results, use_container_width=True)

with tab2:
    c1, c2 = st.columns([1, 4])
    with c1:
        code = st.text_input("输入自选代码", "600519")
        days = st.slider("数据范围", 60, 240, 120)
    
    if code:
        start_date = (pd.Timestamp.now() - pd.Timedelta(days=days+30)).strftime('%Y%m%d')
        df_hist = ak.stock_zh_a_hist(symbol=code, start_date=start_date, adjust="qfq")
        
        if not df_hist.empty:
            df_hist = RadarEngine.calc_indicators(df_hist)
            last = df_hist.iloc[-1]
            prev = df_hist.iloc[-2]

            # 金叉判定弹窗
            if prev['K'] < prev['D'] and last['K'] > last['D']:
                st.success(f"⚡ 实时预警：{code} 今日达成 KDJ 金叉！")
                st.toast("KDJ 金叉触发！", icon="🔥")

            # 绘图
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.6, 0.4], vertical_spacing=0.05)
            fig.add_trace(go.Candlestick(x=df_hist['日期'], open=df_hist['开盘'], high=df_hist['最高'], low=df_hist['最低'], close=df_hist['收盘'], name="K线"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df_hist['日期'], y=df_hist['J'], line=dict(color='purple', width=2), name="KDJ-J"), row=2, col=1)
            fig.add_hline(y=20, line_dash="dot", row=2, col=1)
            fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
