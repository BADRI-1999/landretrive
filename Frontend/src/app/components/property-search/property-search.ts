import { Component, ChangeDetectionStrategy, ChangeDetectorRef } from '@angular/core';
import { Property, SearchResponse } from '../../models/property.models';
import { PropertySearchService } from '../../services/property_service.service';
import { FormsModule } from '@angular/forms';   
import { CommonModule } from '@angular/common'; 

@Component({
  selector: 'app-property-search',
  standalone: true,
  imports: [FormsModule, CommonModule],
  templateUrl: './property-search.html',
  styleUrls: ['./property-search.css'],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class PropertySearchComponent {
  district_name: string = '';
  mandal_name: string = '';
  village_name: string = '';
  survey_no: string = '';

  loading = false;
  errorMsg: string | null = null;
  results: Property[] = [];

  constructor(private propertyService: PropertySearchService, private cdr: ChangeDetectorRef) {}

  onSearch(): void {
    this.errorMsg = null;
    this.results = [];

    if (
      this.district_name == null ||
      this.mandal_name == null ||
      this.village_name == null ||
      !this.survey_no.trim()
    ) {
      this.errorMsg = 'Please enter district, mandal, village IDs and survey number.';
      return;
    }

    console.time('search-call');

    this.loading = true;

    this.propertyService
      .searchByIds(this.district_name, this.mandal_name, this.village_name, this.survey_no.trim())
      .subscribe({
        next: (resp: SearchResponse) => {
          console.timeEnd('search-call');
          
          this.results = resp.results;
          this.loading = false;
          this.cdr.markForCheck();
         
          console.log('Search results', this.results[0]);
        },
        error: (err) => {
        console.timeEnd('search-call');
        this.loading = false;
        this.cdr.markForCheck();
        console.error('Search error', err);
          if (err.status === 404) {
            this.errorMsg = 'No properties found for given filters.';
          } else {
            this.errorMsg = 'Search failed. Please try again.';
            console.error('Search error', err);
          }
        },
      });
  }
}
