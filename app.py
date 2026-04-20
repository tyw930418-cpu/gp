import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import random

# --- 1. 终端配置与视觉 ---
st.set_page_config(page_title="NIQING | 量能雷达", layout="wide")
st.markdown("<style>.stApp { background-color: #0b0e14; color: #e0e0e0; }</style>", unsafe_allow_html=True)

# --- 2. 授权验证 ---
if "auth" not in st.session_state:
    st.markdown("<h2 style='text-align: center; color: #d4af37;'>NIQING STUDIO 策略终端</h2>", unsafe_allow_html=True)
    if st.text_input("授权令牌", type="password") == "niqing888":
        st.session_state.auth = True
        st.rerun()
    st.stop()

# --- 3. 核心策略引擎 ---
class NIQINGEngine:
    @staticmethod
    def is_green_cross(row, sens=0.15):
        """判断绿色十字星：阴线且实体占比小"""
        is_down = row['今开'] > row['最新价']
        entity = abs(row['今开'] - row['最新价'])
        total_range = row['最高'] - row['最低'] + 0.001
        is_cross = (entity / total_range) <= sens
        return is_down and is_cross

    @staticmethod
    def is_kdj_golden(code):
        """判断KDJ金叉：昨日K<D 且 今日K>D"""
        try:
            # 抓取最近30天数据
            df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq").tail(30)
            if len(df) < 10: return False
            low_9, high_9 = df['最低'].rolling(9).min(), df['最高'].rolling(9).max()
            rsv = (df['收盘'] - low_9) / (high_9 - low_9 + 0.001) * 100
            df['K'] = rsv.ewm(com=2, adjust=False).mean()
            df['D'] = df['K'].ewm(com=2, adjust=False).mean()
            return (df.iloc[-2]['K'] < df.iloc[-2]['D']) and (df.iloc[-1]['K'] > df.iloc[-1]['D'])
        except: return False

# --- 4. 侧边栏配置 ---
with st.sidebar:
    st.header("⚙️ 扫描配置")
    scan_limit = st.slider("扫描活跃股数量", 50, 500, 150)
    cross_sens = st.slider("十字星灵敏度", 0.05, 0.3, 0.15)
    min_vol_val = st.number_input("最小成交额(万)", value=8000)

st.title("妮情 · 量能信号实时雷达")

# --- 5. 扫描逻辑 ---
if st.button("🚀 启动全市场【量能+十字星+金叉】扫描"):
    with st.spinner("正在获取全市场实时量能数据..."):
        all_data = ak.stock_zh_a_spot_em()
        # 强制转换数值，处理成交量和成交额
        cols = ['最新价', '涨跌幅', '成交量', '成交额', '最高', '最低', '今开']
        all_data[cols] = all_data[cols].apply(pd.to_numeric, errors='coerce')
        
        # 筛选高活跃度池
        active_pool = all_data[all_data['成交额'] >= min_vol_val * 10000].sort_values('成交额', ascending=False).head(scan_limit)
        
        golden_res, cross_res = [], []
        bar = st.progress(0)
        status_text = st.empty()

        for i, (idx, row) in enumerate(active_pool.iterrows()):
            status_text.text(f"分析中: {row['名称']} ({i+1}/{len(active_pool)})")
            
            # 打包基础数据（含成交量）
            stock_info = {
                "代码": row['代码'],
                "名称": row['名称'],
                "最新价": row['最新价'],
                "涨跌幅%": row['涨跌幅'],
                "成交量(手)": f"{int(row['成交量']):,}", # 格式化显示
                "成交额(亿)": round(row['成交额']/1e8, 2)
            }

            # 判定信号
            if NIQINGEngine.is_green_cross(row, cross_sens):
                cross_res.append(stock_info)
            if NIQINGEngine.is_kdj_golden(row['代码']):
                golden_res.append(stock_info)
            
            bar.progress((i + 1) / len(active_pool))
            time.sleep(0.01) # 极速扫描
        
        st.session_state.g_list = pd.DataFrame(golden_res)
        st.session_state.c_list = pd.DataFrame(cross_res)
        status_text.success(f"扫描完成！捕捉到 {len(golden_res)} 个金叉，{len(cross_res)} 个十字星。")

# --- 6. 结果双屏显示 ---
col_g, col_c = st.columns(2)

with col_g:
    st.markdown("### 📈 今日 KDJ 金叉 (带成交量)")
    if "g_list" in st.session_state and not st.session_state.g_list.empty:
        st.dataframe(st.session_state.g_list, use_container_width=True, height=350)
    else: st.info("无信号")

with col_c:
    st.markdown("### 💹 今日绿色十字星 (带成交量)")
    if "c_list" in st.session_state and not st.session_state.c_list.empty:
        st.dataframe(st.session_state.c_list, use_container_width=True, height=350)
    else: st.info("无信号")

# --- 7. 深度量价回测窗口 ---
st.divider()
st.subheader("🔍 选定个股量价透视")

# 整合可选列表
all_found = []
if "g_list" in st.session_state: all_found += st.session_state.g_list['名称'].tolist()
if "c_list" in st.session_state: all_found += st.session_state.c_list['名称'].tolist()
all_found = list(set(all_found))

if all_found:
    selected = st.selectbox("选择下方列表中的个股查看量能配合情况", all_found)
    
    # 查找代码
    lookup_df = pd.concat([st.session_state.get('g_list', pd.DataFrame()), st.session_state.get('c_list', pd.DataFrame())])
    target_code = lookup_df[lookup_df['名称'] == selected]['代码'].values[0]
    
    with st.spinner(f"加载 {selected} 技术分析图..."):
        h_df = ak.stock_zh_a_hist(symbol=target_code, adjust="qfq").tail(60)
        
        # 创建：价格+成交量+KDJ 三层看板
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.05, 
                            row_heights=[0.7, 0.3])
        
        # 1. 主图：K线
        fig.add_trace(go.Candlestick(x=h_df['日期'], open=h_df['开盘'], high=h_df['最高'], 
                                     low=h_df['最低'], close=h_df['收盘'], name="K线"), row=1, col=1)
        
        # 2. 副图：成交量柱状图 (颜色随行情变动)
        colors = ['#2ecc71' if c > o else '#e74c3c' for c, o in zip(h_df['收盘'], h_df['开盘'])]
        fig.add_trace(go.Bar(x=h_df['日期'], y=h_df['成交量'], marker_color=colors, name="成交量"), row=2, col=1)
        
        fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)
else:
    st.write("等待扫描结果以开启深度透视...")
