import { useEffect, useRef } from 'react';
import * as d3 from 'd3';

const DelayChart = ({ trains }) => {
  const svgRef = useRef(null);

  useEffect(() => {
    if (!trains.length) return;

    const data = trains.map(t => ({
      id: t.id,
      delay: t.delay
    }));

    const width = 300;
    const height = 180;
    const margin = { top: 20, right: 10, bottom: 30, left: 40 };

    // Clear previous chart
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    const x = d3.scaleBand()
      .domain(data.map(d => d.id))
      .range([margin.left, width - margin.right])
      .padding(0.3);

    const y = d3.scaleLinear()
      .domain([0, d3.max(data, d => d.delay) + 5])
      .range([height - margin.bottom, margin.top]);

    // Bars
    svg.selectAll('rect')
      .data(data)
      .join('rect')
      .attr('x', d => x(d.id))
      .attr('y', d => y(d.delay))
      .attr('width', x.bandwidth())
      .attr('height', d => y(0) - y(d.delay))
      .attr('fill', d => d.delay > 5 ? '#ff4444' : '#00ff88')
      .attr('rx', 4);

    // X axis
    svg.append('g')
      .attr('transform', `translate(0,${height - margin.bottom})`)
      .call(d3.axisBottom(x))
      .selectAll('text')
      .style('fill', '#aaa')
      .style('font-size', '10px');

    // Y axis
    svg.append('g')
      .attr('transform', `translate(${margin.left},0)`)
      .call(d3.axisLeft(y).ticks(4))
      .selectAll('text')
      .style('fill', '#aaa');

    // Style axis lines
    svg.selectAll('.domain, .tick line')
      .style('stroke', '#444');

  }, [trains]);

  return (
    <div style={{ background: '#111', borderRadius: '8px', padding: '10px' }}>
      <p style={{ margin: '0 0 8px 0', fontSize: '12px', color: '#aaa' }}>⏱ Delay per Train (mins)</p>
      <svg ref={svgRef} />
    </div>
  );
};

export default DelayChart;