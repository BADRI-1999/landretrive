import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { timeout, catchError } from 'rxjs/operators';
import { environment } from '../environments/environment';
import { SearchResponse } from '../models/property.models';

@Injectable({ providedIn: 'root' })
export class PropertySearchService {
  private readonly baseUrl = environment.apiBaseUrl;

  constructor(private http: HttpClient) {}

  searchByIds(
    district_name: string,
    mandal_name: string,
    village_name: string,
    survey_no: string
  ): Observable<SearchResponse> {
    let params = new HttpParams()
      .set('district', district_name.toString())
      .set('mandal', mandal_name.toString())
      .set('village', village_name.toString())
      .set('survey_no', survey_no);
    console.log(`${this.baseUrl}/properties/search`, { params });
    return this.http
      .get<SearchResponse>(`${this.baseUrl}/properties/search`, { params })
      .pipe(
        timeout(7000), // fail fast if backend doesn't respond in 7s
        catchError((err) => {
          console.error('Search request failed', err);
          return throwError(() => err);
        })
      );
  }
}
