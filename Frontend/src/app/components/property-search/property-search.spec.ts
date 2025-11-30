import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PropertySearchComponent } from './property-search';

describe('PropertySearch', () => {
  let component: PropertySearchComponent;
  let fixture: ComponentFixture<PropertySearchComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PropertySearchComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(PropertySearchComponent);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
