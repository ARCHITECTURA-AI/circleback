import React from 'react'
import { render, screen } from '@testing-library/react'
import Dashboard from '../page'

describe('Dashboard Page', () => {
  it('renders dashboard heading', () => {
    render(<Dashboard />)
    const heading = screen.getByText(/circle back/i)
    expect(heading).toBeInTheDocument()
  })
})
