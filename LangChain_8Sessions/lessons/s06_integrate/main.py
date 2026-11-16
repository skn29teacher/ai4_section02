from common.prompts import build_review_chain
from common.data import first_input
from common.runtime import cli, make_model, run_safely

def main():
    args = cli()
    chain = build_review_chain(make_model(args.mock,args.provider))
    result = chain.invoke(first_input())
    print('보존된 원문:', result['notice'])
    print('초안:', result['draft'])
    print('검토:', result['review'])
    assert {'audience','tone','notice','draft','review'} <= result.keys()

if __name__ == '__main__':
    run_safely(main)
