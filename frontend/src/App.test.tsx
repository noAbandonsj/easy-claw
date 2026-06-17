import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { App } from './App';

describe('App', () => {
  it('renders the Easy Claw frontend shell', () => {
    render(<App />);

    expect(screen.getByRole('heading', { name: 'Local Agent' })).toBeInTheDocument();
    expect(screen.getAllByText('Easy Claw')).toHaveLength(2);
    expect(screen.getByLabelText('Connection status')).toHaveTextContent('Ready');
  });
});
