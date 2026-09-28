import React, { useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { formatDate } from '../format';

export default function UsageChart({ data, loading, bucket }) {
  const [metric, setMetric] = useState('total_tokens');

  if (loading) return <div className="loading state-box">Loading chart...</div>;
  if (!data || data.length === 0) return null;

  const formatXAxis = (tickItem) => {
    const dateObj = new Date(tickItem.endsWith('Z') ? tickItem : tickItem + 'Z');
    if (bucket === 'day') {
      return dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
    return dateObj.toLocaleString('en-US', { hour: '2-digit', minute: '2-digit' });
  };

  const getTooltipFormatter = (value, name) => {
    if (name === 'cost_usd') return [`$${value.toFixed(4)}`, 'Cost'];
    if (name === 'requests') return [value, 'Requests'];
    return [value, 'Tokens'];
  };

  return (
    <div className="chart-container card">
      <div className="chart-header">
        <h3>Usage Chart</h3>
        <select value={metric} onChange={e => setMetric(e.target.value)}>
          <option value="total_tokens">Tokens</option>
          <option value="requests">Requests</option>
          <option value="cost_usd">Cost ($)</option>
        </select>
      </div>
      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
            <XAxis dataKey="bucket_start" tickFormatter={formatXAxis} minTickGap={30} />
            <YAxis />
            <Tooltip 
              formatter={getTooltipFormatter} 
              labelFormatter={(label) => formatDate(label)}
            />
            <Area 
              type="monotone" 
              dataKey={metric} 
              stroke="#3b82f6" 
              fill="#93c5fd" 
              fillOpacity={0.3} 
              isAnimationActive={false} // Disable animation to feel snappier
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
