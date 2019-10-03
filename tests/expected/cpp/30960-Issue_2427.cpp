namespace C { enum { Value }; }

void f( int a )
{
	bool ok;

	// Issue #2151
	ok = ( a & C::Value ) && true;
	// Issue #2427
	ok = ( a & C::Value ) and true;
	ok = ( a & C::Value ) == 0;
	ok = ( a & C::Value ) + 0;
	ok = ( a & C::Value ) xor 1;
	ok = ( a & C::Value ) ^ 1;
}
