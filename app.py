import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
import time

# --- 1. 界面与风格 ---
st.set_page_config(page_title="NIQING | 全能抗压雷达", layout="wide")

# --- 2. 核心数据抓取（带备用源逻辑） ---
def fetch_data_with_retry():
    """一级尝试：东方财富；二级尝试：新浪"""
    try:
        # 尝试东财源
        df = ak.stock_zh_a_spot_em()
        if not df.empty: return df, "东方财富"
    except:
        try:
            # 东财挂了，自动切换新浪源
            df = ak.stock_zh_a_spot_sina()
            if not df.empty: return df, "新浪财经"
        except:
            return None, None

def get_hist_safe(symbol):
    """抓取历史K线，增加频率保护"""
    try:
        time.sleep(0.3) # 冷却防止连环封
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq").tail(40)
        return df
    except:
        return None

# --- 3. 左侧控制中心 (Sidebar) ---
with st.sidebar:
    st.title("妮情 · 策略控制台")
    st.divider()
    
    # 模块 1
    st.subheader("🔍 个股搜索窗口")
    search_code = st.text_input("代码搜索", placeholder="输入后回车", key="s_1")
    
    st.divider()
    
    # 模块 2
    st.subheader("🟢 阴线十字星监控")
    vol_star = st.number_input("准入额 (亿)", value=5.0)
    btn_star = st.button("全场同步信号", key="b_star")
    
    st.divider()
    
    # 模块 3
    st.subheader("⚡ 金叉行情预警")
    vol_gold = st.number_input("金叉门槛 (亿)", value=8.0)
    btn_gold = st.button("全场深度预警", key="b_gold")
    
    st.divider()
    if st.button("♻️ 强制重置连接"):
        st.cache_data.clear()
        st.rerun()

# --- 4. 右侧结果大屏 ---
st.header("NIQING STUDIO · 实时监测中心")

# A. 搜索逻辑
if search_code:
    with st.spinner("🚀 正在穿透数据源..."):
        h_df = get_hist_safe(search_code)
        if h_df is not None:
            fig = go.Figure(data=[go.Candlestick(x=h_df['日期'], open=h_df['开盘'], 
                            high=h_df['最高'], low=h_df['最低'], close=h_df['收盘'])])
            fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("⚠️ 连线中断：当前所有数据源均无法响应，请点击左侧重置。")

# B. 阴线十字星扫描 (带动态查找动画)
if btn_star:
    with st.status("🔍 正在扫描全市场阴线信号...", expanded=True) as status:
        st.write("正在探测可用数据服务器...")
        spot, source = fetch_data_with_retry()
        if spot is not None:
            st.write(f"成功连接至【{source}】数据源，开始形态匹配...")
            spot['成交额'] = pd.to_numeric(spot['成交额'], errors='coerce')
            pool = spot[spot['成交额'] >= vol_star * 100000000].copy()
            
            p_bar = st.progress(0)
            res = []
            for i, (idx, row) in enumerate(pool.iterrows()):
                p_bar.progress((i + 1) / len(pool))
                o, c, h, l = row['今开'], row['最新价'], row['最高'], row['最低']
                if c < o and (h-l) > 0:
                    if (abs(o-c)/(h-l)) <= 0.15:
                        res.append({"代码":row['代码'], "名称":row['名称'], "最新价":c, "跌幅%":row['涨跌幅'], "量额(亿)":round(row['成交额']/1e8, 2)})
            
            if res:
                st.dataframe(pd.DataFrame(res), use_container_width=True)
                status.update(label=f"✅ {source} 信号同步完成", state="complete")
            else:
                st.warning("信号池为空")
        else:
            status.update(label="❌ 报警：全网源繁忙，请稍后再试", state="error")

# C. 金叉预警扫描
if btn_gold:
    with st.status("⚡ 启动深度趋势识别...", expanded=True) as status:
        spot, source = fetch_data_with_retry()
        if spot is not None:
            spot['成交额'] = pd.to_numeric(spot['成交额'], errors='coerce')
            pool = spot[spot['成交额'] >= vol_gold * 100000000].sort_values('成交额', ascending=False).head(25)
            
            g_bar = st.progress(0)
            gold_res = []
            for i, (idx, row) in enumerate(pool.iterrows()):
                g_bar.progress((i + 1) / len(pool))
                st.write(f"正在穿透: {row['名称']}")
                df_h = get_hist_safe(row['代码'])
                if df_h is not None and len(df_h) >= 15:
                    # KDJ 计算
                    low_9 = df_h['最低'].rolling(9).min()
                    high_9 = df_h['最高'].rolling(9).max()
                    rsv = (df_h['收盘'] - low_9) / (high_9 - low_9) * 100
                    k = rsv.ewm(com=2).mean()
                    d = k.ewm(com=2).mean()
                    j = 3 * k - 2 * d
                    if j.iloc[-1] > d.iloc[-1] and j.iloc[-2] <= d.iloc[-2]:
                        gold_res.append({"代码":row['代码'], "名称":row['名称'], "J值":round(j.iloc[-1],2), "成交额(亿)":round(row['成交额']/1e8, 2)})
            
            if gold_res:
                st.dataframe(pd.DataFrame(gold_res), use_container_width=True)
                status.update(label="✅ 趋势识别完成", state="complete")
            else:
                st.info("当前暂无强势金叉信号")
        else:
            status.update(label="❌ 数据链路崩溃", state="error")
