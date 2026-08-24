'use client';

/**
 * Organization Assistance Ticket Queue Component
 * Allows supervisors to view, acknowledge, and resolve worker assistance tickets in real-time.
 */

import React, { useState, useEffect } from 'react';
import { AssistanceTicket } from '@/shared/types';
import { api } from '@/shared/api/client';

export function AssistanceTicketQueue() {
  const [tickets, setTickets] = useState<AssistanceTicket[]>([]);

  useEffect(() => {
    async function loadTickets() {
      const data = await api.getPendingAssistanceTickets();
      setTickets(data);
    }
    loadTickets();
  }, []);

  const handleResolve = (ticketId: string) => {
    setTickets((prev) => prev.filter((t) => t.id !== ticketId));
  };

  return (
    <div className="glass-panel" style={{ padding: '1.75rem', borderRadius: '18px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ color: 'var(--accent-amber)' }}>⚠️</span> Supervisor Assistance Queue
          </h2>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Priority-tagged requests from active assembly stations
          </span>
        </div>
        <span className="badge badge-rose">{tickets.length} Pending</span>
      </div>

      {tickets.length === 0 ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          ✅ All assistance tickets resolved. Assembly lines operating normally.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {tickets.map((ticket) => (
            <div
              key={ticket.id}
              className="glass-card"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '1rem',
                borderLeft: `4px solid ${
                  ticket.priority === 'high' || ticket.priority === 'critical'
                    ? 'var(--accent-rose)'
                    : 'var(--accent-amber)'
                }`,
              }}
            >
              <div style={{ flex: '1 1 300px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                  <span className={ticket.priority === 'high' ? 'badge badge-rose' : 'badge badge-cyan'}>
                    {ticket.priority.toUpperCase()}
                  </span>
                  <strong style={{ color: 'white' }}>{ticket.stationName}</strong>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>({ticket.workerName})</span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>• {ticket.createdAt}</span>
                </div>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-primary)' }}>{ticket.description}</p>
              </div>

              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => handleResolve(ticket.id)}
                  className="btn btn-success"
                  style={{ minHeight: '38px', padding: '0.4rem 0.9rem', fontSize: '0.85rem' }}
                >
                  ✓ Acknowledge & Resolve
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
