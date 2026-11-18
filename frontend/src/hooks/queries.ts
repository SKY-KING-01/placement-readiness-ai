import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';

export function useAPI<T>(path: string, enabled = true) {
  return useQuery({ queryKey: [path], queryFn: () => api<T>(path), enabled,
    retry: false, staleTime: 15000 });
}
